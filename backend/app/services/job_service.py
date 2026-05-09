"""
Job service — create and enqueue jobs.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, Job, JobStatus
from app.workers.queue import QUEUE_CHAPTERS, QUEUE_COMPILE, QUEUE_OUTLINES, get_queue

logger = structlog.get_logger(__name__)


async def enqueue_outline(
    db: AsyncSession,
    book: Book,
    notes_before: str = "",
) -> Job:
    """Create a job record and enqueue outline generation."""
    job = Job(
        book_id=book.id,
        task_name="generate_outline",
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.flush()  # get the id

    queue = get_queue(QUEUE_OUTLINES)
    queue.enqueue(
        "app.workers.tasks.generate_outline_task",
        job_id_arg := job.id,
        notes_before,
        job_id=job.id,  # use our job id as RQ job id for easy lookup
        job_timeout=600,  # 10 min max
    )

    logger.info("outline_enqueued", job_id=job.id, book_id=book.id)
    return job


async def enqueue_chapter(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
) -> Job:
    """Create a job record and enqueue chapter generation."""
    job = Job(
        book_id=book.id,
        task_name="generate_chapter",
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.flush()

    queue = get_queue(QUEUE_CHAPTERS)
    queue.enqueue(
        "app.workers.tasks.generate_chapter_task",
        job.id,
        chapter_number,
        job_id=job.id,
        job_timeout=900,  # 15 min max per chapter
    )

    logger.info("chapter_enqueued", job_id=job.id, book_id=book.id, chapter=chapter_number)
    return job


async def enqueue_compile(
    db: AsyncSession,
    book: Book,
    output_format: str = "docx",
) -> Job:
    """Create a job record and enqueue compilation."""
    job = Job(
        book_id=book.id,
        task_name="compile_book",
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.flush()

    queue = get_queue(QUEUE_COMPILE)
    queue.enqueue(
        "app.workers.tasks.compile_book_task",
        job.id,
        output_format,
        job_id=job.id,
        job_timeout=300,
    )

    logger.info("compile_enqueued", job_id=job.id, book_id=book.id)
    return job


async def get_job(db: AsyncSession, job_id: str) -> Job | None:
    from sqlalchemy import select
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()
