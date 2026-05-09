"""
RQ task functions.

Each task:
1. Opens a synchronous DB session (RQ workers are sync)
2. Fetches the job record and marks it RUNNING
3. Runs the appropriate service
4. Marks the job DONE or FAILED
5. Writes any output/errors to the job record

Streaming: the provider's stream() output is appended to job.streamed_output
so the SSE endpoint can poll and push incremental updates to the frontend.
"""

import asyncio
import traceback
from datetime import datetime

import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Book, BookStatus, Job, JobStatus, OutputFormat, User
from app.providers.factory import get_provider_for_user
from app.services import outline_service, chapter_service, compiler_service

logger = structlog.get_logger(__name__)


def _get_sync_engine():
    """
    Create a synchronous SQLAlchemy engine for use in RQ worker tasks.
    RQ workers run in a sync context so we can't use asyncpg directly.
    We swap the driver to psycopg2 for sync workers.
    """
    sync_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    ).replace(
        "sqlite+aiosqlite://", "sqlite://"
    )
    return create_engine(sync_url)


def _append_stream(session: Session, job: Job, text: str) -> None:
    """Append text to the job's streamed_output buffer."""
    job.streamed_output = (job.streamed_output or "") + text
    session.add(job)
    session.commit()


def _mark_running(session: Session, job: Job) -> None:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    session.add(job)
    session.commit()


def _mark_done(session: Session, job: Job) -> None:
    job.status = JobStatus.DONE
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()


def _mark_failed(session: Session, job: Job, error: str) -> None:
    job.status = JobStatus.FAILED
    job.completed_at = datetime.utcnow()
    job.error_message = error
    session.add(job)
    session.commit()


def _run_async(coro):
    """Run an async coroutine from a sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Task functions ────────────────────────────────────────────────────────────

def generate_outline_task(job_id: str, notes_before: str = "") -> None:
    """
    RQ task: generate outline for a book.
    Called by the worker process.
    """
    engine = _get_sync_engine()
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            logger.error("job_not_found", job_id=job_id)
            return

        book = session.get(Book, job.book_id)
        user = session.get(User, book.user_id)

        _mark_running(session, job)
        logger.info("outline_task_started", job_id=job_id, book_id=book.id)

        try:
            provider = get_provider_for_user(user)

            # Use async outline service via asyncio
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

            async_engine = create_async_engine(settings.database_url)
            async_factory = async_sessionmaker(async_engine, expire_on_commit=False)

            async def _run():
                async with async_factory() as async_session:
                    async_book = await async_session.get(Book, job.book_id)
                    result = await outline_service.generate_outline(
                        db=async_session,
                        book=async_book,
                        provider=provider,
                        notes_before=notes_before or async_book.outline_raw or "",
                    )
                    await async_session.commit()
                    return result

            outline_text = asyncio.run(_run())
            _append_stream(session, job, outline_text)
            _mark_done(session, job)

            # Update book status in sync session
            book.status = BookStatus.OUTLINE_REVIEW
            session.add(book)
            session.commit()

            logger.info("outline_task_done", job_id=job_id)

        except Exception as exc:
            error = traceback.format_exc()
            logger.error("outline_task_failed", job_id=job_id, error=str(exc))
            _mark_failed(session, job, error)

            book.status = BookStatus.FAILED
            session.add(book)
            session.commit()


def generate_chapter_task(job_id: str, chapter_number: int) -> None:
    """RQ task: generate a single chapter."""
    engine = _get_sync_engine()
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            return

        book = session.get(Book, job.book_id)
        user = session.get(User, book.user_id)

        _mark_running(session, job)
        logger.info("chapter_task_started", job_id=job_id, chapter=chapter_number)

        try:
            provider = get_provider_for_user(user)

            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
            async_engine = create_async_engine(settings.database_url)
            async_factory = async_sessionmaker(async_engine, expire_on_commit=False)

            async def _run():
                async with async_factory() as async_session:
                    async_book = await async_session.get(Book, job.book_id)
                    chapter = await chapter_service.get_chapter(
                        async_session, job.book_id, chapter_number
                    )
                    await chapter_service.generate_chapter(
                        db=async_session,
                        book=async_book,
                        chapter=chapter,
                        provider=provider,
                    )
                    await async_session.commit()
                    return chapter.content or ""

            content = asyncio.run(_run())
            _append_stream(session, job, content)
            _mark_done(session, job)
            logger.info("chapter_task_done", job_id=job_id, chapter=chapter_number)

        except Exception as exc:
            error = traceback.format_exc()
            logger.error("chapter_task_failed", job_id=job_id, error=str(exc))
            _mark_failed(session, job, error)


def compile_book_task(job_id: str, output_format: str = "docx") -> None:
    """RQ task: compile book to docx/txt."""
    engine = _get_sync_engine()
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            return

        book = session.get(Book, job.book_id)
        _mark_running(session, job)

        try:
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
            async_engine = create_async_engine(settings.database_url)
            async_factory = async_sessionmaker(async_engine, expire_on_commit=False)

            fmt = OutputFormat.DOCX if output_format == "docx" else OutputFormat.TXT

            async def _run():
                async with async_factory() as async_session:
                    async_book = await async_session.get(Book, job.book_id)
                    path = await compiler_service.compile_book(
                        db=async_session,
                        book=async_book,
                        output_format=fmt,
                    )
                    await async_session.commit()
                    return path

            path = asyncio.run(_run())
            _append_stream(session, job, f"Compiled to: {path}")
            _mark_done(session, job)

            book.status = BookStatus.COMPLETE
            session.add(book)
            session.commit()

            logger.info("compile_task_done", job_id=job_id, path=path)

        except Exception as exc:
            error = traceback.format_exc()
            logger.error("compile_task_failed", job_id=job_id, error=str(exc))
            _mark_failed(session, job, error)
