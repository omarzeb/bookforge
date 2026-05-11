"""
Pydantic schemas for API request/response bodies.
"""

from datetime import datetime
from pydantic import BaseModel
from app.db.models import BookStatus, OutputFormat


# ── Book schemas ──────────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str
    selected_model: str | None = None
    notes_before: str = ""
    chapter_count: int = 10


class BookResponse(BaseModel):
    id: str
    title: str
    status: BookStatus
    selected_model: str | None
    outline_raw: str | None
    outline_approved: bool
    compiled_path: str | None
    output_format: OutputFormat | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdvanceRequest(BaseModel):
    notes_before: str = ""


# ── Outline schemas ───────────────────────────────────────────────────────────

class OutlineReviseRequest(BaseModel):
    revision_notes: str


# ── Chapter schemas ───────────────────────────────────────────────────────────

class ChapterResponse(BaseModel):
    id: str
    book_id: str
    number: int
    title: str
    content: str | None
    summary: str | None
    approved: bool
    revision_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterReviseRequest(BaseModel):
    notes: str


# ── Final review schemas ──────────────────────────────────────────────────────

class FinalReviseRequest(BaseModel):
    notes: str
