"""
Book routes — updated for Phase 6 async job enqueueing.

advance() now returns a job_id immediately instead of blocking.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.rate_limit import user_limiter
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
from app.services import book_service, outline_service
from app.services import job_service

logger = structlog.get_logger(__name__)


router = APIRouter(prefix="/books", tags=["books"])


class AdvanceResponse(BaseModel):
    book: BookResponse
    job_id: str | None = None
    message: str = ""


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
    # Validate model_id against known models — prevents bypass of cost tiers
    if body.selected_model:
        from app.services.model_tiers import CURATED_MODEL_IDS
        from sqlalchemy import select as _select
        from app.db.models import ModelCache as _ModelCache
        cached = await db.execute(_select(_ModelCache.model_id))
        known_ids = CURATED_MODEL_IDS | {row[0] for row in cached.fetchall()}
        if body.selected_model not in known_ids:
            raise HTTPException(
                status_code=422,
                detail="Unknown model — sync models list first via /api/v1/models/sync"
            )

    book = await book_service.create_book(
        db=db,
        user_id=user.id,
        title=body.title,
        selected_model=body.selected_model,
    )
    # Store notes_before with chapter count hint so outline service picks it up
    notes = body.notes_before or ""
    if body.chapter_count and (body.chapter_count != 10 or not notes):
        notes = f"{notes} (write exactly {body.chapter_count} chapters)"
    if notes:
        book.outline_raw = notes
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


# ── Advance — now async via job queue ────────────────────────────────────────

@user_limiter.limit("10/minute")
@router.post("/{book_id}/advance", response_model=AdvanceResponse)
async def advance_book(
    book_id: str,
    body: AdvanceRequest = AdvanceRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AdvanceResponse:
    """
    Enqueue the next generation step for this book.
    Returns immediately with a job_id — poll GET /jobs/{id} for status,
    or connect to GET /jobs/{id}/stream for live token output.
    """
    book = await book_service.get_book(db, book_id, user.id)

    # Auto-transition CHAPTER_REVIEW → CHAPTERS_GENERATING if all approved
    from app.services import chapter_service as cs
    if book.status == BookStatus.CHAPTER_REVIEW:
        if await cs.all_approved(db, book.id):
            book.status = BookStatus.CHAPTERS_GENERATING
            db.add(book)
            await db.commit()
            await db.refresh(book)

    job_id: str | None = None
    message = ""

    if book.status == BookStatus.INPUT_RECEIVED:
        try:
            get_provider_for_user(user)  # validate key exists before enqueueing
        except InvalidKey as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        job = await job_service.enqueue_outline(
            db=db,
            book=book,
            notes_before=body.notes_before or book.outline_raw or "",
        )
        job_id = job.id
        message = "Outline generation queued"

    elif book.status == BookStatus.CHAPTERS_GENERATING:
        from app.services import chapter_service as cs
        await cs.initialize_chapters(db, book)
        next_ch = await cs.get_next_pending(db, book.id)

        if next_ch is None:
            # Check for chapters needing revision
            chapters = await cs.get_chapters(db, book.id)
            needs_revision = [c for c in chapters if c.revision_notes and not c.approved]

            if needs_revision:
                ch = needs_revision[0]
                job = await job_service.enqueue_chapter(db=db, book=book, chapter_number=ch.number)
                job_id = job.id
                message = f"Chapter {ch.number} revision queued"
            elif await cs.all_approved(db, book.id):
                # All done — compile
                job = await job_service.enqueue_compile(db=db, book=book)
                job_id = job.id
                message = "Compilation queued"
            else:
                book.status = BookStatus.CHAPTER_REVIEW
                db.add(book)
                message = "All chapters generated — awaiting review"
        else:
            job = await job_service.enqueue_chapter(
                db=db, book=book, chapter_number=next_ch.number
            )
            job_id = job.id
            message = f"Chapter {next_ch.number} generation queued"

    elif book.status == BookStatus.FINAL_REVIEW:
        job = await job_service.enqueue_compile(db=db, book=book)
        job_id = job.id
        message = "Compilation queued"

    else:
        message = f"Book is in state '{book.status}' — no action needed"

    await db.commit()
    await db.refresh(book)

    return AdvanceResponse(
        book=BookResponse.model_validate(book),
        job_id=job_id,
        message=message,
    )


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


@user_limiter.limit("10/minute")
@router.post("/{book_id}/outline/revise", response_model=AdvanceResponse)
async def revise_outline(
    book_id: str,
    body: OutlineReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AdvanceResponse:
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.OUTLINE_REVIEW)

    try:
        get_provider_for_user(user)
    except InvalidKey as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job = await job_service.enqueue_outline(
        db=db,
        book=book,
        notes_before=body.revision_notes,
    )
    await db.commit()
    await db.refresh(book)

    return AdvanceResponse(
        book=BookResponse.model_validate(book),
        job_id=job.id,
        message="Outline revision queued",
    )


# ── Final review subroutes ────────────────────────────────────────────────────

@router.post("/{book_id}/final-review/approve", response_model=AdvanceResponse)
async def approve_final_review(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AdvanceResponse:
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.FINAL_REVIEW)

    job = await job_service.enqueue_compile(db=db, book=book)
    await db.commit()
    await db.refresh(book)

    return AdvanceResponse(
        book=BookResponse.model_validate(book),
        job_id=job.id,
        message="Compilation queued",
    )


@router.post("/{book_id}/final-review/revise", response_model=BookResponse)
async def revise_final_review(
    book_id: str,
    body: FinalReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    book = await book_service.get_book(db, book_id, user.id)
    _require_book_status(book, BookStatus.FINAL_REVIEW)
    book.status = BookStatus.CHAPTER_REVIEW
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


# ── Compile + download ────────────────────────────────────────────────────────

@user_limiter.limit("5/minute")
@router.post("/{book_id}/compile", response_model=AdvanceResponse)
async def compile_book(
    book_id: str,
    output_format: OutputFormat = OutputFormat.DOCX,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AdvanceResponse:
    book = await book_service.get_book(db, book_id, user.id)
    job = await job_service.enqueue_compile(
        db=db, book=book, output_format=output_format.value
    )
    await db.commit()
    await db.refresh(book)
    return AdvanceResponse(
        book=BookResponse.model_validate(book),
        job_id=job.id,
        message="Compilation queued",
    )


@router.get("/{book_id}/download")
async def download_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    book = await book_service.get_book(db, book_id, user.id)

    if not book.compiled_path:
        raise HTTPException(status_code=404, detail="Book has not been compiled yet")

    from app.config import settings as _settings
    if _settings.storage_backend.value == "s3":
        # Generate a presigned S3 URL and redirect
        import boto3
        s3 = boto3.client("s3", region_name=_settings.aws_region)
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": _settings.aws_s3_bucket, "Key": book.compiled_path},
                ExpiresIn=300,  # 5 minute download window
            )
        except Exception:
            raise HTTPException(status_code=404, detail="Compiled file not found")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)

    import os
    # Local storage: validate path stays within output directory
    output_dir = os.path.realpath("/app/output")
    safe_path = os.path.realpath(book.compiled_path)
    if not safe_path.startswith(output_dir + os.sep):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="Compiled file not found on disk")

    media_types = {
        OutputFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        OutputFormat.TXT: "text/plain",
    }
    media_type = media_types.get(book.output_format, "application/octet-stream")

    return FileResponse(
        path=safe_path,
        media_type=media_type,
        filename=os.path.basename(book.compiled_path),
    )
