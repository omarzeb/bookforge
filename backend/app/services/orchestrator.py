"""
Book generation orchestrator — iterative state machine.

Rewritten from recursive to iterative to avoid stack overflows on long books
and to make the flow easier to trace in logs.

run(book, provider, db) advances the book through states until it either:
  - Reaches a WAITING state (needs human input) → returns the current state
  - Completes → returns BookStatus.COMPLETE
  - Hits an error → raises and marks book as FAILED
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, BookStatus
from app.providers.base import LLMProvider
from app.services import (
    book_service,
    chapter_service,
    compiler_service,
    outline_service,
)

logger = structlog.get_logger(__name__)

# States where we stop and wait for human input
WAITING_STATES = {
    BookStatus.OUTLINE_REVIEW,
    BookStatus.CHAPTER_REVIEW,
    # FINAL_REVIEW is NOT a waiting state — orchestrator auto-compiles once all chapters approved
    BookStatus.COMPLETE,
    BookStatus.FAILED,
}

MAX_ITERATIONS = 200  # safety cap to prevent infinite loops


async def run(
    db: AsyncSession,
    book: Book,
    provider: LLMProvider,
    notes_before: str = "",
    output_format: str = "docx",
) -> BookStatus:
    """
    Advance the book through as many state transitions as possible.
    Stops when it hits a state requiring human input.
    Returns the final state after this run.
    """
    iterations = 0

    while iterations < MAX_ITERATIONS:
        iterations += 1
        state = book.status

        logger.info(
            "orchestrator_tick",
            book_id=book.id,
            state=state,
            iteration=iterations,
        )

        # ── Stop conditions ───────────────────────────────────────────────────
        if state in WAITING_STATES:
            logger.info("orchestrator_waiting", book_id=book.id, state=state)
            return state

        # ── INPUT_RECEIVED: generate the outline ─────────────────────────────
        if state == BookStatus.INPUT_RECEIVED:
            await outline_service.generate_outline(
                db=db,
                book=book,
                provider=provider,
                notes_before=notes_before or book.outline_raw or "",
            )
            await db.commit()
            await db.refresh(book)
            continue

        # ── OUTLINE_REVIEW: waiting for human — stop here ─────────────────────
        # (reached via WAITING_STATES above)

        # ── CHAPTERS_GENERATING: generate next pending chapter ────────────────
        if state == BookStatus.CHAPTERS_GENERATING:
            # Ensure chapter records exist
            count = await chapter_service.initialize_chapters(db, book)

            next_ch = await chapter_service.get_next_pending(db, book.id)

            if next_ch is None:
                # Check for chapters needing revision
                chapters = await chapter_service.get_chapters(db, book.id)
                needs_revision = [c for c in chapters if c.revision_notes and not c.approved]

                if needs_revision:
                    ch = needs_revision[0]
                    await chapter_service.generate_chapter(db, book, ch, provider)
                    await db.commit()
                    continue

                # All generated — check approval
                if await chapter_service.all_approved(db, book.id):
                    book.status = BookStatus.FINAL_REVIEW
                    db.add(book)
                    await db.commit()
                    await db.refresh(book)
                else:
                    book.status = BookStatus.CHAPTER_REVIEW
                    db.add(book)
                    await db.commit()
                    await db.refresh(book)
                continue

            await chapter_service.generate_chapter(db, book, next_ch, provider)
            await db.commit()
            await db.refresh(book)
            continue

        # ── CHAPTER_REVIEW: waiting for human — stop here ─────────────────────
        # (reached via WAITING_STATES above)

        # ── FINAL_REVIEW: all chapters approved — compile ─────────────────────
        if state == BookStatus.FINAL_REVIEW:
            from app.db.models import OutputFormat as OF
            fmt = OF.DOCX if output_format == "docx" else OF.TXT
            await compiler_service.compile_book(db=db, book=book, output_format=fmt)
            await db.commit()
            await db.refresh(book)
            continue

        # ── COMPILING: transitional state set by compiler ─────────────────────
        if state == BookStatus.COMPILING:
            # Should not normally land here — compiler sets COMPLETE directly
            book.status = BookStatus.COMPLETE
            db.add(book)
            await db.commit()
            await db.refresh(book)
            continue

        # ── Unknown state ─────────────────────────────────────────────────────
        logger.error("orchestrator_unknown_state", book_id=book.id, state=state)
        book.status = BookStatus.FAILED
        db.add(book)
        await db.commit()
        return BookStatus.FAILED

    # Exceeded iteration cap
    logger.error("orchestrator_max_iterations", book_id=book.id)
    book.status = BookStatus.FAILED
    db.add(book)
    await db.commit()
    return BookStatus.FAILED
