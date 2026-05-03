"""
Book CRUD — all operations scoped to user_id.
No method here ever touches a book belonging to a different user.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import NotFoundError
from app.db.models import Book, BookStatus, OutputFormat

logger = structlog.get_logger(__name__)


async def get_book(db: AsyncSession, book_id: str, user_id: str) -> Book:
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.user_id == user_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise NotFoundError(f"Book {book_id} not found")
    return book


async def list_books(db: AsyncSession, user_id: str) -> list[Book]:
    result = await db.execute(
        select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())
    )
    return list(result.scalars().all())


async def create_book(
    db: AsyncSession,
    user_id: str,
    title: str,
    selected_model: str | None = None,
) -> Book:
    book = Book(
        user_id=user_id,
        title=title,
        status=BookStatus.INPUT_RECEIVED,
        selected_model=selected_model,
    )
    db.add(book)
    await db.flush()  # gets the generated id without committing
    logger.info("book_created", book_id=book.id, user_id=user_id, title=title)
    return book


async def delete_book(db: AsyncSession, book_id: str, user_id: str) -> None:
    book = await get_book(db, book_id, user_id)
    await db.delete(book)
    logger.info("book_deleted", book_id=book_id)


async def update_book_status(
    db: AsyncSession, book: Book, status: BookStatus
) -> Book:
    book.status = status
    db.add(book)
    return book
