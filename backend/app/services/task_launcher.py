"""
Task launcher — wraps ECS Fargate run_task() for production,
falls back to RQ for local development.

In production: API writes job to DB → calls launch_task() →
  boto3 starts a one-shot Fargate container with --job-id
  → container runs orchestrator → writes results back to DB → exits.

In local dev: falls back to RQ so you don't need AWS credentials.

The caller never needs to know which backend is being used.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Book, Job, JobStatus

logger = structlog.get_logger(__name__)

# ECS config — these are set via env vars in production (App Runner injects them)
# Left empty in local dev since we use RQ instead
ECS_CLUSTER = ""
ECS_TASK_DEFINITION = ""
ECS_SUBNET_IDS: list[str] = []
ECS_SECURITY_GROUP_IDS: list[str] = []


def _load_ecs_config() -> None:
    """Load ECS config from settings at runtime (not at import time)."""
    global ECS_CLUSTER, ECS_TASK_DEFINITION, ECS_SUBNET_IDS, ECS_SECURITY_GROUP_IDS
    ECS_CLUSTER = getattr(settings, "ecs_cluster", "")
    ECS_TASK_DEFINITION = getattr(settings, "ecs_task_definition", "")
    subnets = getattr(settings, "ecs_subnet_ids", "")
    sgs = getattr(settings, "ecs_security_group_ids", "")
    ECS_SUBNET_IDS = [s.strip() for s in subnets.split(",") if s.strip()] if subnets else []
    ECS_SECURITY_GROUP_IDS = [s.strip() for s in sgs.split(",") if s.strip()] if sgs else []


def _is_fargate_available() -> bool:
    """Return True if we have enough config to launch Fargate tasks."""
    _load_ecs_config()
    return bool(ECS_CLUSTER and ECS_TASK_DEFINITION and ECS_SUBNET_IDS)


async def launch_task(
    db: AsyncSession,
    job: Job,
    extra_env: dict[str, str] | None = None,
) -> str | None:
    """
    Launch a one-shot worker for this job.

    Production: launches a Fargate task, returns the ECS task ARN.
    Local dev: enqueues to RQ, returns None.

    The job record already exists in DB before this is called.
    """
    if settings.is_production and _is_fargate_available():
        return await _launch_fargate(db, job, extra_env or {})
    else:
        _launch_rq(job, extra_env or {})
        return None


async def _launch_fargate(
    db: AsyncSession,
    job: Job,
    extra_env: dict[str, str],
) -> str:
    """Launch a one-shot Fargate task for this job."""
    import boto3

    ecs = boto3.client("ecs", region_name=settings.aws_region)

    env_overrides = [
        {"name": "JOB_ID", "value": job.id},
        *[{"name": k, "value": v} for k, v in extra_env.items()],
    ]

    try:
        response = ecs.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=ECS_TASK_DEFINITION,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": ECS_SUBNET_IDS,
                    "securityGroups": ECS_SECURITY_GROUP_IDS,
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": "bookforge-worker",
                        "command": ["--job-id", job.id],
                        "environment": env_overrides,
                    }
                ]
            },
        )

        failures = response.get("failures", [])
        if failures:
            raise RuntimeError(f"ECS run_task failures: {failures}")

        tasks = response.get("tasks", [])
        if not tasks:
            raise RuntimeError("ECS run_task returned no tasks")

        task_arn = tasks[0]["taskArn"]

        # Store the ARN for observability
        job.ecs_task_arn = task_arn
        db.add(job)

        logger.info(
            "fargate_task_launched",
            job_id=job.id,
            task_arn=task_arn,
            task_definition=ECS_TASK_DEFINITION,
        )
        return task_arn

    except Exception as exc:
        logger.error("fargate_launch_failed", job_id=job.id, error=str(exc))
        # Mark job as failed so SSE stream can report it
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to launch Fargate task: {exc}"
        db.add(job)
        raise


def _launch_rq(job: Job, extra_env: dict[str, str]) -> None:
    """
    Fallback for local dev: enqueue to RQ.
    Maps task_name → RQ task function.
    """
    from app.workers.queue import get_queue, QUEUE_OUTLINES, QUEUE_CHAPTERS, QUEUE_COMPILE
    from app.workers import tasks as worker_tasks

    task_map = {
        "generate_outline": (QUEUE_OUTLINES, worker_tasks.generate_outline_task, 600),
        "generate_chapter": (QUEUE_CHAPTERS, worker_tasks.generate_chapter_task, 900),
        "compile_book":     (QUEUE_COMPILE,  worker_tasks.compile_book_task,     300),
    }

    queue_name, task_fn, timeout = task_map.get(
        job.task_name,
        ("default", worker_tasks.generate_outline_task, 600),
    )

    queue = get_queue(queue_name)

    # Build kwargs from extra_env so chapter_number, notes_before etc. are passed
    kwargs: dict = {}
    if "NOTES_BEFORE" in extra_env:
        kwargs["notes_before"] = extra_env["NOTES_BEFORE"]
    if "CHAPTER_NUMBER" in extra_env:
        kwargs["chapter_number"] = int(extra_env["CHAPTER_NUMBER"])
    if "OUTPUT_FORMAT" in extra_env:
        kwargs["output_format"] = extra_env["OUTPUT_FORMAT"]

    queue.enqueue(
        task_fn,
        job.id,
        job_id=job.id,
        job_timeout=timeout,
        **kwargs,
    )

    logger.info("rq_task_enqueued", job_id=job.id, task=job.task_name, queue=queue_name)


async def reconcile_stuck_jobs(db: AsyncSession, timeout_minutes: int = 30) -> int:
    """
    Mark RUNNING jobs that haven't completed within timeout as FAILED.
    Called by EventBridge every hour as a defensive measure.
    Returns count of jobs marked failed.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select, update
    from app.db.models import JobStatus

    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)

    result = await db.execute(
        select(Job)
        .where(
            Job.status == JobStatus.RUNNING,
            Job.started_at < cutoff,
        )
    )
    stuck_jobs = result.scalars().all()

    for job in stuck_jobs:
        job.status = JobStatus.FAILED
        job.error_message = f"Job timed out after {timeout_minutes} minutes"
        db.add(job)
        logger.warning("job_marked_stuck", job_id=job.id, started_at=job.started_at)

    if stuck_jobs:
        await db.commit()
        logger.info("reconciliation_complete", stuck_count=len(stuck_jobs))

    return len(stuck_jobs)
