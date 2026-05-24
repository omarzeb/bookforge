"""
Excel ingestion route.
"""

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas import BookResponse
from app.services.book_service import get_book
from app.services.ingest_service import ingest_excel

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/books", tags=["ingest"])


@router.post("/ingest-excel", response_model=list[BookResponse], status_code=201)
async def ingest_excel_upload(
    request: Request,
    file: UploadFile = File(..., description="Excel file with 'title' column"),
    selected_model: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list:
    """
    Upload an Excel file to create multiple books at once.
    Required column: title
    Optional column: notes_on_outline_before
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=422, detail="File must be an Excel file (.xlsx or .xls)")

    # Check Content-Length before reading to prevent OOM on huge uploads
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        book_ids = await ingest_excel(
            db=db,
            user_id=user.id,
            file_bytes=contents,
            selected_model=selected_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await db.commit()

    books = [await get_book(db, bid, user.id) for bid in book_ids]
    return books
