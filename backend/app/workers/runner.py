"""
RQ worker entry point.

Starts a worker that listens on all named queues.
In Phase 7 this becomes a one-shot Fargate task runner.

Usage:
    python -m app.workers.runner              # normal worker
    python -m app.workers.runner --job-id X  # one-shot mode (Phase 7)
"""

import argparse
import logging

import structlog
from rq import Worker

from app.workers.queue import QUEUE_CHAPTERS, QUEUE_COMPILE, QUEUE_DEFAULT, QUEUE_OUTLINES, get_redis_conn

logger = structlog.get_logger(__name__)


def run_worker() -> None:
    """Start an RQ worker listening on all queues."""
    logging.basicConfig(level=logging.INFO)
    conn = get_redis_conn()

    queues = [QUEUE_OUTLINES, QUEUE_CHAPTERS, QUEUE_COMPILE, QUEUE_DEFAULT]
    logger.info("worker_starting", queues=queues)

    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)


def run_one_shot(job_id: str) -> None:
    """
    Phase 7 mode: execute a single job by ID and exit.
    Used when launched as a Fargate one-shot task.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from app.config import settings
    from app.db.models import Job

    logger.info("one_shot_starting", job_id=job_id)

    async def _run():
        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                logger.error("one_shot_job_not_found", job_id=job_id)
                return

            # Dispatch to correct task based on task_name
            from app.workers.tasks import (
                generate_outline_task,
                generate_chapter_task,
                compile_book_task,
            )

            task_map = {
                "generate_outline": generate_outline_task,
                "generate_chapter": generate_chapter_task,
                "compile_book": compile_book_task,
            }

            task_fn = task_map.get(job.task_name)
            if not task_fn:
                logger.error("unknown_task", task_name=job.task_name)
                return

            task_fn(job_id)

    asyncio.run(_run())
    logger.info("one_shot_complete", job_id=job_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="BookForge worker")
    parser.add_argument("--job-id", help="Run a single job and exit (Fargate mode)")
    args = parser.parse_args()

    if args.job_id:
        run_one_shot(args.job_id)
    else:
        run_worker()


if __name__ == "__main__":
    main()
