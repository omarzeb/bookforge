"""
Pydantic schemas for API request/response bodies.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import BookStatus, OutputFormat


# ── Book schemas ──────────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    selected_model: str | None = Field(None, max_length=200)
    notes_before: str = Field("", max_length=5000)
    chapter_count: int = Field(10, ge=1, le=50)


class BookResponse(BaseModel):
    id: str
    title: str                          # no Field bounds on response models
    status: BookStatus
    selected_model: str | None
    outline_raw: str | None
    outline_approved: bool
    # compiled_path intentionally omitted — internal filesystem path
    output_format: OutputFormat | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdvanceRequest(BaseModel):
    notes_before: str = Field("", max_length=5000)


# ── Outline schemas ───────────────────────────────────────────────────────────

class OutlineReviseRequest(BaseModel):
    revision_notes: str = Field(..., min_length=1, max_length=5000)


# ── Chapter schemas ───────────────────────────────────────────────────────────

class ChapterResponse(BaseModel):
    id: str
    book_id: str
    number: int
    title: str                          # no Field bounds on response models
    content: str | None
    summary: str | None
    approved: bool
    revision_notes: str | None = None   # correct optional type
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterReviseRequest(BaseModel):
    notes: str = Field(..., min_length=1, max_length=5000)


# ── Final review schemas ──────────────────────────────────────────────────────

class FinalReviseRequest(BaseModel):
    notes: str = Field(..., min_length=1, max_length=5000)
