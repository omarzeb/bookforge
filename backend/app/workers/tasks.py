"""
Worker task functions — one-shot Fargate pattern.

Each task function:
1. Marks the job RUNNING
2. Runs the service (async, via asyncio.run)
3. Writes streamed output to job.streamed_output
4. Marks DONE or FAILED

In production these run inside a Fargate container launched with --job-id.
In local dev they run inside the RQ worker process.
"""

import asyncio
import traceback
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


def _run(coro):
    """Run async coroutine from sync RQ worker context."""
    return asyncio.run(coro)


def _get_async_session():
    """Return a fresh async session factory."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from app.config import settings
    engine = create_async_engine(settings.database_url)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def generate_outline_task(job_id: str, notes_before: str = "") -> None:
    """One-shot task: generate outline for a book."""

    async def _run_async():
        factory = _get_async_session()
        async with factory() as db:
            from app.db.models import Book, BookStatus, Job, JobStatus, User
            from app.providers.factory import get_provider_for_user
            from app.services import outline_service

            job = await db.get(Job, job_id)
            if not job:
                logger.error("job_not_found", job_id=job_id)
                return

            book = await db.get(Book, job.book_id)
            user = await db.get(User, book.user_id)

            # Mark running
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.add(job)
            await db.commit()

            logger.info("outline_task_started", job_id=job_id, book_id=book.id)

            try:
                provider = get_provider_for_user(user)
                outline = await outline_service.generate_outline(
                    db=db,
                    book=book,
                    provider=provider,
                    notes_before=notes_before or book.outline_raw or "",
                )
                await db.commit()

                job.status = JobStatus.DONE
                job.completed_at = datetime.utcnow()
                job.streamed_output = outline
                db.add(job)
                await db.commit()

                logger.info("outline_task_done", job_id=job_id)

            except Exception as exc:
                error = traceback.format_exc()
                logger.error("outline_task_failed", job_id=job_id, error=str(exc))

                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = error
                db.add(job)

                book.status = BookStatus.FAILED
                db.add(book)
                await db.commit()

    _run(_run_async())


def generate_chapter_task(job_id: str, chapter_number: int = 0) -> None:
    """One-shot task: generate a single chapter."""

    async def _run_async():
        factory = _get_async_session()
        async with factory() as db:
            from app.db.models import Book, Job, JobStatus, User
            from app.providers.factory import get_provider_for_user
            from app.services import chapter_service

            job = await db.get(Job, job_id)
            if not job:
                return

            book = await db.get(Book, job.book_id)
            user = await db.get(User, book.user_id)

            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.add(job)
            await db.commit()

            logger.info("chapter_task_started", job_id=job_id, chapter=chapter_number)

            try:
                provider = get_provider_for_user(user)
                chapter = await chapter_service.get_chapter(db, book.id, chapter_number)
                await chapter_service.generate_chapter(
                    db=db, book=book, chapter=chapter, provider=provider
                )
                await db.commit()

                job.status = JobStatus.DONE
                job.completed_at = datetime.utcnow()
                job.streamed_output = chapter.content or ""
                db.add(job)
                await db.commit()

                logger.info("chapter_task_done", job_id=job_id, chapter=chapter_number)

            except Exception as exc:
                error = traceback.format_exc()
                logger.error("chapter_task_failed", job_id=job_id, error=str(exc))

                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = error
                db.add(job)
                await db.commit()

    _run(_run_async())


def compile_book_task(job_id: str, output_format: str = "docx") -> None:
    """One-shot task: compile book to docx/txt."""

    async def _run_async():
        factory = _get_async_session()
        async with factory() as db:
            from app.db.models import Book, BookStatus, Job, JobStatus, OutputFormat
            from app.services import compiler_service

            job = await db.get(Job, job_id)
            if not job:
                return

            book = await db.get(Book, job.book_id)

            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.add(job)
            await db.commit()

            logger.info("compile_task_started", job_id=job_id)

            try:
                fmt = OutputFormat.DOCX if output_format == "docx" else OutputFormat.TXT
                path = await compiler_service.compile_book(
                    db=db, book=book, output_format=fmt
                )
                await db.commit()

                job.status = JobStatus.DONE
                job.completed_at = datetime.utcnow()
                job.streamed_output = f"Compiled: {path}"
                db.add(job)
                await db.commit()

                logger.info("compile_task_done", job_id=job_id, path=path)

            except Exception as exc:
                error = traceback.format_exc()
                logger.error("compile_task_failed", job_id=job_id, error=str(exc))

                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = error
                db.add(job)
                await db.commit()

    _run(_run_async())
