"""
ORM models — all tables in one file for now.

Each model maps 1:1 to a database table.
Alembic reads these to generate migrations.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

class BookStatus(str, enum.Enum):
    INPUT_RECEIVED      = "INPUT_RECEIVED"
    OUTLINE_GENERATING  = "OUTLINE_GENERATING"
    OUTLINE_REVIEW      = "OUTLINE_REVIEW"
    CHAPTERS_GENERATING = "CHAPTERS_GENERATING"
    CHAPTER_REVIEW      = "CHAPTER_REVIEW"
    FINAL_REVIEW        = "FINAL_REVIEW"
    COMPILING           = "COMPILING"
    COMPLETE            = "COMPLETE"
    FAILED              = "FAILED"


class JobStatus(str, enum.Enum):
    QUEUED   = "QUEUED"
    RUNNING  = "RUNNING"
    DONE     = "DONE"
    FAILED   = "FAILED"


class OutputFormat(str, enum.Enum):
    DOCX = "docx"
    TXT  = "txt"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    # Encrypted OpenRouter key (Fernet) — null until user saves their key
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    books: Mapped[list["Book"]] = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    usage_logs: Mapped[list["UsageLog"]] = relationship("UsageLog", back_populates="user")
    prompt_overrides: Mapped[list["PromptOverride"]] = relationship("PromptOverride", back_populates="user")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[BookStatus] = mapped_column(Enum(BookStatus), default=BookStatus.INPUT_RECEIVED, nullable=False)
    selected_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Raw outline text from LLM, then parsed
    outline_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    outline_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # S3 key or local path to compiled artifact
    compiled_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    output_format: Mapped[OutputFormat | None] = mapped_column(Enum(OutputFormat), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="books")
    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="book", cascade="all, delete-orphan", order_by="Chapter.number")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="book", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # used for context chaining
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (UniqueConstraint("book_id", "number", name="uq_chapter_book_number"),)

    book: Mapped["Book"] = relationship("Book", back_populates="chapters")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "generate_outline"

    # ECS task ARN — populated in Phase 7 when Fargate launches the task
    ecs_task_arn: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Streaming output buffer — worker appends tokens, SSE endpoint polls and streams
    streamed_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    book: Mapped["Book"] = relationship("Book", back_populates="jobs")


class ModelCache(Base):
    """
    Cached list of models from OpenRouter's /models endpoint.
    Refreshed periodically by a background task (Phase 3).
    """
    __tablename__ = "model_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_price_per_1k: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_price_per_1k: Mapped[float | None] = mapped_column(Float, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Recommended/Budget/Premium/Other
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class PromptOverride(Base):
    """
    Per-user prompt customisation per stage.
    If a row exists, it overrides the default prompt for that (user, stage) combo.
    """
    __tablename__ = "prompt_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "outline", "chapter", "summary"
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "stage", name="uq_prompt_user_stage"),)

    user: Mapped["User"] = relationship("User", back_populates="prompt_overrides")


class UsageLog(Base):
    """
    Every LLM call is logged here for the per-user usage/spend dashboard.
    """
    __tablename__ = "usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="usage_logs")
