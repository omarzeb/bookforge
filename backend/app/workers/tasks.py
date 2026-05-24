"""
Worker task functions — one-shot Fargate pattern.
"""

import asyncio
import traceback
from datetime import UTC, datetime

import structlog

logger = structlog.get_logger(__name__)


def _run(coro):
    return asyncio.run(coro)


def _get_async_session():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from app.config import settings
    engine = create_async_engine(settings.database_url)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def generate_outline_task(job_id: str, notes_before: str = "") -> None:

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

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC)
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
                job.completed_at = datetime.now(UTC)
                job.streamed_output = outline
                db.add(job)
                await db.commit()

                logger.info("outline_task_done", job_id=job_id)

            except Exception as exc:
                logger.error("outline_task_failed", job_id=job_id, error=str(exc),
                             traceback=traceback.format_exc())

                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                job.error_message = f"Outline generation failed: {type(exc).__name__}"
                db.add(job)

                book.status = BookStatus.FAILED
                db.add(book)
                await db.commit()

    _run(_run_async())


def generate_chapter_task(job_id: str, chapter_number: int = 0) -> None:
    """
    Generate a chapter. Initializes chapters first if they don't exist yet.
    chapter_number comes from env var as string in Fargate — cast to int.
    """
    chapter_number = int(chapter_number)  # safe cast from env var string

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
            job.started_at = datetime.now(UTC)
            db.add(job)
            await db.commit()

            logger.info("chapter_task_started", job_id=job_id, chapter=chapter_number)

            try:
                provider = get_provider_for_user(user)

                # Always initialize chapters first — idempotent, safe to call multiple times
                await chapter_service.initialize_chapters(db, book)
                await db.commit()
                await db.refresh(book)

                # chapter_number=0 means "find the next unwritten chapter"
                if chapter_number == 0:
                    chapter = await chapter_service.get_next_pending(db, book.id)
                    if chapter is None:
                        # Check for chapters needing revision
                        chapters = await chapter_service.get_chapters(db, book.id)
                        chapter = next(
                            (c for c in chapters if c.revision_notes and not c.approved),
                            None
                        )
                    if chapter is None:
                        logger.warning("no_pending_chapter", job_id=job_id)
                        job.status = JobStatus.DONE
                        job.completed_at = datetime.now(UTC)
                        job.streamed_output = "No pending chapters found"
                        db.add(job)
                        await db.commit()
                        return
                else:
                    chapter = await chapter_service.get_chapter(db, book.id, chapter_number)

                await chapter_service.generate_chapter(
                    db=db, book=book, chapter=chapter, provider=provider
                )
                await db.commit()

                job.status = JobStatus.DONE
                job.completed_at = datetime.now(UTC)
                job.streamed_output = chapter.content or ""
                db.add(job)
                await db.commit()

                logger.info("chapter_task_done", job_id=job_id, chapter=chapter.number)

            except Exception as exc:
                logger.error("chapter_task_failed", job_id=job_id, error=str(exc),
                             traceback=traceback.format_exc())

                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                job.error_message = f"Chapter generation failed: {type(exc).__name__}"
                db.add(job)
                await db.commit()

    _run(_run_async())


def compile_book_task(job_id: str, output_format: str = "docx") -> None:

    async def _run_async():
        factory = _get_async_session()
        async with factory() as db:
            from app.db.models import Book, Job, JobStatus, OutputFormat
            from app.services import compiler_service

            job = await db.get(Job, job_id)
            if not job:
                return

            book = await db.get(Book, job.book_id)

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC)
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
                job.completed_at = datetime.now(UTC)
                job.streamed_output = "Compiled successfully"  # path intentionally omitted
                db.add(job)
                await db.commit()

                logger.info("compile_task_done", job_id=job_id, path=path)

            except Exception as exc:
                logger.error("compile_task_failed", job_id=job_id, error=str(exc),
                             traceback=traceback.format_exc())

                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                job.error_message = f"Compilation failed: {type(exc).__name__}"
                db.add(job)
                await db.commit()

    _run(_run_async())
