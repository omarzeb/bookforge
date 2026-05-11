"""
Outline service — generation and review logic.
Ported from outline_manager.py.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ConflictError, ValidationError
from app.db.models import Book, BookStatus, PromptOverride
from app.parsers.outline_parser import NUDGE_PROMPT, parse_outline
from app.parsers.text_cleaner import clean_text
from app.prompts import resolve_outline
from app.providers.base import LLMProvider
from app.services.book_service import update_book_status

logger = structlog.get_logger(__name__)

MAX_PARSE_RETRIES = 2


async def _get_user_override(db: AsyncSession, user_id: str, stage: str) -> str | None:
    result = await db.execute(
        select(PromptOverride).where(
            PromptOverride.user_id == user_id,
            PromptOverride.stage == stage,
        )
    )
    override = result.scalar_one_or_none()
    return override.prompt_text if override else None


async def generate_outline(
    db: AsyncSession,
    book: Book,
    provider: LLMProvider,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
) -> str:
    """
    Generate or regenerate an outline for the book.
    Returns the raw outline text.
    Raises ValidationError if the outline can't be parsed after retries.
    """
    if not notes_before.strip():
        raise ValidationError(
            "Cannot generate outline: no guidance notes provided. "
            "Add notes before generating."
        )

    model_id = book.selected_model or "defaults"
    override = await _get_user_override(db, book.user_id, "outline")

    # Extract chapter count hint from notes if specified
    import re
    chapter_match = re.search(r'\b(\d+)\s+chapters?\b', notes_before, re.IGNORECASE)
    chapter_count = int(chapter_match.group(1)) if chapter_match else 10

    prompt = resolve_outline(
        model_id=model_id,
        title=book.title,
        notes_before=notes_before,
        notes_after=notes_after,
        previous_outline=previous_outline,
        user_override=override,
        chapter_count=chapter_count,
    )

    logger.info("generating_outline", book_id=book.id, model=model_id)
    result = await provider.generate(
        model=model_id,
        system=prompt["system"],
        user=prompt["user"],
        max_tokens=2048,
        user_id=book.user_id,
        book_id=book.id,
        stage="outline",
        db=db,
    )

    outline_text = clean_text(result.content)

    # Validate we can parse it — retry with nudge prompt if not
    parsed = parse_outline(outline_text)
    if not parsed:
        for attempt in range(MAX_PARSE_RETRIES):
            logger.warning("outline_parse_retry", attempt=attempt + 1, book_id=book.id)
            nudge_result = await provider.generate(
                model=model_id,
                system=prompt["system"],
                user=NUDGE_PROMPT + "\n\n" + outline_text,
                max_tokens=2048,
            )
            outline_text = clean_text(nudge_result.content)
            parsed = parse_outline(outline_text)
            if parsed:
                break
        else:
            raise ValidationError(
                "Outline could not be parsed after multiple attempts. "
                "Try a different model or adjust your prompt."
            )

    book.outline_raw = outline_text
    book.status = BookStatus.OUTLINE_REVIEW
    book.outline_approved = False
    db.add(book)

    logger.info("outline_generated", book_id=book.id, chapters=len(parsed))
    return outline_text


async def approve_outline(db: AsyncSession, book: Book) -> Book:
    """Mark the outline as approved and advance state."""
    if book.status != BookStatus.OUTLINE_REVIEW:
        raise ConflictError(f"Book is in state {book.status}, not OUTLINE_REVIEW")
    if not book.outline_raw:
        raise ConflictError("No outline to approve")

    book.outline_approved = True
    book.status = BookStatus.CHAPTERS_GENERATING
    db.add(book)
    logger.info("outline_approved", book_id=book.id)
    return book


async def revise_outline(
    db: AsyncSession,
    book: Book,
    provider: LLMProvider,
    revision_notes: str,
) -> str:
    """Regenerate the outline with editor revision notes."""
    if not book.outline_raw:
        raise ConflictError("No existing outline to revise")

    return await generate_outline(
        db=db,
        book=book,
        provider=provider,
        notes_before=book.outline_raw.split("\n")[0],  # reuse original notes
        notes_after=revision_notes,
        previous_outline=book.outline_raw,
    )
