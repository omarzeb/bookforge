"""
Book routes — full workflow via HTTP.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.exception_handlers import ConflictError, NotFoundError, ValidationError
from app.db.models import Book, BookStatus, OutputFormat, User
from app.db.session import get_db
from app.providers.exceptions import InvalidKey
from app.providers.factory import get_provider_for_user
from app.schemas import (
    AdvanceRequest,
    BookCreate,
    BookResponse,
    FinalReviseRequest,
    OutlineReviseRequest,
)
from app.services import book_service, compiler_service, orchestrator, outline_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/books", tags=["books"])


def _require_book_status(book: Book, *allowed: BookStatus) -> None:
    if book.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Book is in state '{book.status}' — expected one of {[s.value for s in allowed]}",
        )


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[BookResponse])
async def list_books(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Book]:
    return await book_service.list_books(db, user.id)


@router.post("", response_model=BookResponse, status_code=201)
async def create_book(
    body: BookCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    book = await book_service.create_book(
        db=db,
        user_id=user.id,
        title=body.title,
        selected_model=body.selected_model,
    )
    # Store notes_before in outline_raw until outline generation picks it up
    if body.notes_before:
        book.outline_raw = body.notes_before
        db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    return await book_service.get_book(db, book_id, user.id)


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await book_service.delete_book(db, book_id, user.id)
    await db.commit()


# ── Advance (run orchestrator) ─────────────────────────────────────────────────

@router.post("/{book_id}/advance", response_model=BookResponse)
async def advance_book(
    book_id: str,
    body: AdvanceRequest = AdvanceRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    """
    Run the orchestrator for this book. Advances through automatic states
    until it hits a human gate (OUTLINE_REVIEW, CHAPTER_REVIEW) or completes.
    """
    book = await book_service.get_book(db, book_id, user.id)

    # If all chapters are approved and we are in CHAPTER_REVIEW,
    # transition back to CHAPTERS_GENERATING so the orchestrator can proceed
    from app.services import chapter_service as cs
    if book.status == BookStatus.CHAPTER_REVIEW:
        if await cs.all_approved(db, book.id):
            book.status = BookStatus.CHAPTERS_GENERATING
            db.add(book)
            await db.commit()
            await db.refresh(book)

    try:
        provider = get_provider_for_user(user)
    except InvalidKey as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await orchestrator.run(
        db=db,
        book=book,
        provider=provider,
        notes_before=body.notes_before or book.outline_raw or "",
    )
    await db.refresh(book)
    return book


# ── Outline subroutes ─────────────────────────────────────────────────────────

@router.post("/{book_id}/outline/approve", response_model=BookResponse)
async def approve_outline(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.OUTLINE_REVIEW)
    await outline_service.approve_outline(db=db, book=book)
    await db.commit()
    await db.refresh(book)
    return book


@router.post("/{book_id}/outline/revise", response_model=BookResponse)
async def revise_outline(
    book_id: str,
    body: OutlineReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.OUTLINE_REVIEW)

    try:
        provider = get_provider_for_user(user)
    except InvalidKey as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await outline_service.revise_outline(
        db=db, book=book, provider=provider, revision_notes=body.revision_notes
    )
    await db.commit()
    await db.refresh(book)
    return book


# ── Final review subroutes ────────────────────────────────────────────────────

@router.post("/{book_id}/final-review/approve", response_model=BookResponse)
async def approve_final_review(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    """Approve the final review and compile the book."""
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.FINAL_REVIEW)

    await compiler_service.compile_book(db=db, book=book)
    await db.commit()
    await db.refresh(book)
    return book


@router.post("/{book_id}/final-review/revise", response_model=BookResponse)
async def revise_final_review(
    book_id: str,
    body: FinalReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    """Send the book back for chapter revision with final notes."""
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.FINAL_REVIEW)

    # Attach notes to the book and revert to chapter review
    book.status = BookStatus.CHAPTER_REVIEW
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


# ── Compile + download ────────────────────────────────────────────────────────

@router.post("/{book_id}/compile", response_model=BookResponse)
async def compile_book(
    book_id: str,
    output_format: OutputFormat = OutputFormat.DOCX,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    book = await book_service.get_book(db, book_id, user.id)
    await compiler_service.compile_book(db=db, book=book, output_format=output_format)
    await db.commit()
    await db.refresh(book)
    return book


@router.get("/{book_id}/download")
async def download_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    book = await book_service.get_book(db, book_id, user.id)

    if not book.compiled_path:
        raise HTTPException(status_code=404, detail="Book has not been compiled yet")

    import os
    if not os.path.exists(book.compiled_path):
        raise HTTPException(status_code=404, detail="Compiled file not found on disk")

    media_types = {
        OutputFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        OutputFormat.TXT: "text/plain",
    }
    media_type = media_types.get(book.output_format, "application/octet-stream")

    return FileResponse(
        path=book.compiled_path,
        media_type=media_type,
        filename=os.path.basename(book.compiled_path),
    )
