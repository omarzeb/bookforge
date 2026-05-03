"""
Chapter routes.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import BookStatus, Chapter, User
from app.db.session import get_db
from app.providers.exceptions import InvalidKey
from app.providers.factory import get_provider_for_user
from app.schemas import ChapterResponse, ChapterReviseRequest
from app.services import book_service, chapter_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/books", tags=["chapters"])


@router.get("/{book_id}/chapters", response_model=list[ChapterResponse])
async def list_chapters(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Chapter]:
    await book_service.get_book(db, book_id, user.id)  # ownership check
    return await chapter_service.get_chapters(db, book_id)


@router.get("/{book_id}/chapters/{number}", response_model=ChapterResponse)
async def get_chapter(
    book_id: str,
    number: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Chapter:
    await book_service.get_book(db, book_id, user.id)
    return await chapter_service.get_chapter(db, book_id, number)


@router.post("/{book_id}/chapters/{number}/approve", response_model=ChapterResponse)
async def approve_chapter(
    book_id: str,
    number: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Chapter:
    await book_service.get_book(db, book_id, user.id)
    chapter = await chapter_service.get_chapter(db, book_id, number)

    if not chapter.content:
        raise HTTPException(status_code=409, detail="Chapter has no content to approve")

    await chapter_service.approve_chapter(db=db, chapter=chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.post("/{book_id}/chapters/{number}/revise", response_model=ChapterResponse)
async def revise_chapter(
    book_id: str,
    number: int,
    body: ChapterReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Chapter:
    """
    Mark a chapter for revision with notes.
    The next call to POST /books/{id}/advance will regenerate it.
    """
    book = await book_service.get_book(db, book_id, user.id)
    chapter = await chapter_service.get_chapter(db, book_id, number)

    await chapter_service.request_revision(db=db, chapter=chapter, notes=body.notes)

    # Revert book status so orchestrator picks it up on next advance
    if book.status not in (BookStatus.CHAPTERS_GENERATING, BookStatus.CHAPTER_REVIEW):
        book.status = BookStatus.CHAPTERS_GENERATING
        db.add(book)

    await db.commit()
    await db.refresh(chapter)
    return chapter
