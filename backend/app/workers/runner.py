"""
Worker entry point.

Two modes:
  Normal (local dev RQ):  python -m app.workers.runner
  One-shot (Fargate):     python -m app.workers.runner --job-id <id>

In production, Fargate launches this with --job-id.
The container reads the job record, runs the task, writes results, exits.
"""

import argparse
import logging
import os

import structlog

logger = structlog.get_logger(__name__)


def run_one_shot(job_id: str) -> None:
    """
    Fargate mode: execute one job by ID and exit.
    The task_name on the Job record determines which task function runs.
    """
    import asyncio
    from app.core.logging import configure_logging

    configure_logging()
    logger.info("one_shot_starting", job_id=job_id)

    async def _get_task_name() -> str:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
        from app.config import settings
        from app.db.models import Job

        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as db:
            job = await db.get(Job, job_id)
            if not job:
                raise RuntimeError(f"Job {job_id} not found")
            return job.task_name

    task_name = asyncio.run(_get_task_name())

    from app.workers.tasks import (
        compile_book_task,
        generate_chapter_task,
        generate_outline_task,
    )

    task_map = {
        "generate_outline": generate_outline_task,
        "generate_chapter": generate_chapter_task,
        "compile_book":     compile_book_task,
    }

    task_fn = task_map.get(task_name)
    if not task_fn:
        raise RuntimeError(f"Unknown task name: {task_name}")

    # Read extra args from environment (Fargate passes them via container env override)
    kwargs: dict = {}
    if task_name == "generate_outline":
        kwargs["notes_before"] = os.environ.get("NOTES_BEFORE", "")
    elif task_name == "generate_chapter":
        kwargs["chapter_number"] = int(os.environ.get("CHAPTER_NUMBER", "0"))
    elif task_name == "compile_book":
        kwargs["output_format"] = os.environ.get("OUTPUT_FORMAT", "docx")

    task_fn(job_id, **kwargs)
    logger.info("one_shot_complete", job_id=job_id)


def run_worker() -> None:
    """Local dev mode: start an RQ worker listening on all queues."""
    from app.core.logging import configure_logging
    from app.workers.queue import (
        QUEUE_CHAPTERS,
        QUEUE_COMPILE,
        QUEUE_DEFAULT,
        QUEUE_OUTLINES,
        get_redis_conn,
    )
    from rq import Worker

    configure_logging()
    conn = get_redis_conn()
    queues = [QUEUE_OUTLINES, QUEUE_CHAPTERS, QUEUE_COMPILE, QUEUE_DEFAULT]
    logger.info("worker_starting", queues=queues)

    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="BookForge worker")
    parser.add_argument("--job-id", help="Run one job and exit (Fargate one-shot mode)")
    args = parser.parse_args()

    if args.job_id:
        run_one_shot(args.job_id)
    else:
        run_worker()


if __name__ == "__main__":
    main()
