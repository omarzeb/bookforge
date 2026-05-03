"""
Chapter service — generation, context chaining, summary, review.
Ported from chapter_manager.py.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ConflictError, NotFoundError
from app.db.models import Book, Chapter, PromptOverride
from app.parsers.text_cleaner import clean_chapter
from app.parsers.outline_parser import parse_outline
from app.prompts import resolve_chapter, resolve_chapter_revision, resolve_summary
from app.providers.base import LLMProvider

logger = structlog.get_logger(__name__)


async def _get_override(db: AsyncSession, user_id: str, stage: str) -> str | None:
    result = await db.execute(
        select(PromptOverride).where(
            PromptOverride.user_id == user_id,
            PromptOverride.stage == stage,
        )
    )
    o = result.scalar_one_or_none()
    return o.prompt_text if o else None


async def initialize_chapters(db: AsyncSession, book: Book) -> int:
    """
    Parse the approved outline and create Chapter records.
    Idempotent — skips if chapters already exist.
    """
    if not book.outline_raw:
        raise ConflictError("Book has no outline to initialize chapters from")

    result = await db.execute(
        select(Chapter).where(Chapter.book_id == book.id)
    )
    existing = list(result.scalars().all())
    if existing:
        logger.info("chapters_already_exist", book_id=book.id, count=len(existing))
        return len(existing)

    titles = parse_outline(book.outline_raw)
    if not titles:
        raise ConflictError("Could not parse chapters from outline")

    for i, title in enumerate(titles, 1):
        db.add(Chapter(
            book_id=book.id,
            number=i,
            title=title,
            approved=False,
        ))

    await db.flush()
    logger.info("chapters_initialized", book_id=book.id, count=len(titles))
    return len(titles)


async def get_chapters(db: AsyncSession, book_id: str) -> list[Chapter]:
    result = await db.execute(
        select(Chapter)
        .where(Chapter.book_id == book_id)
        .order_by(Chapter.number)
    )
    return list(result.scalars().all())


async def get_chapter(db: AsyncSession, book_id: str, number: int) -> Chapter:
    result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == number)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise NotFoundError(f"Chapter {number} not found")
    return chapter


async def get_previous_summaries(
    db: AsyncSession, book_id: str, before_number: int
) -> list[dict]:
    """Return summaries of all chapters before `before_number`."""
    result = await db.execute(
        select(Chapter)
        .where(Chapter.book_id == book_id, Chapter.number < before_number)
        .order_by(Chapter.number)
    )
    chapters = result.scalars().all()
    return [
        {
            "chapter_number": c.number,
            "chapter_title": c.title,
            "summary": c.summary or "",
        }
        for c in chapters
        if c.summary
    ]


async def get_next_pending(db: AsyncSession, book_id: str) -> Chapter | None:
    """Return the lowest-numbered chapter that hasn't been generated yet."""
    result = await db.execute(
        select(Chapter)
        .where(Chapter.book_id == book_id, Chapter.content == None)  # noqa: E711
        .order_by(Chapter.number)
    )
    return result.scalars().first()


async def generate_chapter(
    db: AsyncSession,
    book: Book,
    chapter: Chapter,
    provider: LLMProvider,
) -> Chapter:
    """
    Generate content for a single chapter with context chaining.
    Handles both first-time generation and revision (if revision_notes set).
    """
    model_id = book.selected_model or "defaults"
    summaries = await get_previous_summaries(db, book.id, chapter.number)

    if chapter.revision_notes and chapter.content:
        # Revision path
        override = await _get_override(db, book.user_id, "chapter_revision")
        prompt = resolve_chapter_revision(
            model_id=model_id,
            book_title=book.title,
            outline=book.outline_raw or "",
            chapter_title=chapter.title,
            chapter_number=chapter.number,
            previous_summaries=summaries,
            original_content=chapter.content,
            editor_notes=chapter.revision_notes,
            user_override=override,
        )
        logger.info("revising_chapter", book_id=book.id, chapter=chapter.number)
    else:
        # Fresh generation
        override = await _get_override(db, book.user_id, "chapter")
        prompt = resolve_chapter(
            model_id=model_id,
            book_title=book.title,
            outline=book.outline_raw or "",
            chapter_title=chapter.title,
            chapter_number=chapter.number,
            previous_summaries=summaries,
            chapter_notes=chapter.revision_notes or "",
            user_override=override,
        )
        logger.info("generating_chapter", book_id=book.id, chapter=chapter.number)

    result = await provider.generate(
        model=model_id,
        system=prompt["system"],
        user=prompt["user"],
        max_tokens=8192,
    )

    content = clean_chapter(result.content)

    # Immediately summarize for context chaining
    summary = await _summarize(
        db=db,
        book=book,
        chapter=chapter,
        provider=provider,
        content=content,
    )

    chapter.content = content
    chapter.summary = summary
    chapter.approved = False
    chapter.revision_notes = None  # clear after applying
    db.add(chapter)

    logger.info("chapter_generated", book_id=book.id, chapter=chapter.number)
    return chapter


async def _summarize(
    db: AsyncSession,
    book: Book,
    chapter: Chapter,
    provider: LLMProvider,
    content: str,
) -> str:
    model_id = book.selected_model or "defaults"
    override = await _get_override(db, book.user_id, "summary")
    prompt = resolve_summary(
        model_id=model_id,
        chapter_content=content,
        chapter_number=chapter.number,
        chapter_title=chapter.title,
        user_override=override,
    )
    result = await provider.generate(
        model=model_id,
        system=prompt["system"],
        user=prompt["user"],
        max_tokens=512,
    )
    return result.content.strip()


async def approve_chapter(db: AsyncSession, chapter: Chapter) -> Chapter:
    chapter.approved = True
    chapter.revision_notes = None
    db.add(chapter)
    return chapter


async def request_revision(
    db: AsyncSession, chapter: Chapter, notes: str
) -> Chapter:
    chapter.approved = False
    chapter.revision_notes = notes
    db.add(chapter)
    return chapter


async def all_approved(db: AsyncSession, book_id: str) -> bool:
    chapters = await get_chapters(db, book_id)
    return bool(chapters) and all(c.approved for c in chapters)
