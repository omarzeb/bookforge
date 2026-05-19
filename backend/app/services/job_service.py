"""
Job service — create job records and dispatch to the appropriate launcher.

Phase 7: launch_task() replaces direct RQ enqueueing.
The launcher decides whether to use Fargate (prod) or RQ (local dev).
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, Job, JobStatus

logger = structlog.get_logger(__name__)


async def _create_job(db: AsyncSession, book: Book, task_name: str) -> Job:
    job = Job(
        book_id=book.id,
        task_name=task_name,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.flush()  # get the generated id
    return job


async def enqueue_outline(
    db: AsyncSession,
    book: Book,
    notes_before: str = "",
) -> Job:
    from app.services.task_launcher import launch_task
    job = await _create_job(db, book, "generate_outline")
    await launch_task(db, job, extra_env={"NOTES_BEFORE": notes_before})
    logger.info("outline_dispatched", job_id=job.id, book_id=book.id)
    return job


async def enqueue_chapter(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
) -> Job:
    from app.services.task_launcher import launch_task
    job = await _create_job(db, book, "generate_chapter")
    await launch_task(db, job, extra_env={"CHAPTER_NUMBER": str(chapter_number)})
    logger.info("chapter_dispatched", job_id=job.id, book_id=book.id, chapter=chapter_number)
    return job


async def enqueue_compile(
    db: AsyncSession,
    book: Book,
    output_format: str = "docx",
) -> Job:
    from app.services.task_launcher import launch_task
    job = await _create_job(db, book, "compile_book")
    await launch_task(db, job, extra_env={"OUTPUT_FORMAT": output_format})
    logger.info("compile_dispatched", job_id=job.id, book_id=book.id)
    return job


async def get_job(db: AsyncSession, job_id: str) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()
