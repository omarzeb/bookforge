"""
Prompt resolver.

resolve(stage, model_id, user, db) → {"system": ..., "user": ...}

Resolution order:
  1. User override from PromptOverride table (if one exists for this stage)
  2. Model-family-specific prompt (claude/ for claude-*, defaults/ for everything else)
  3. Default prompt

Supported stages: "outline", "chapter", "chapter_revision", "summary"
Supported model families: "claude", "default"
"""

from __future__ import annotations

import importlib
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.models import User

logger = structlog.get_logger(__name__)


def _family(model_id: str) -> str:
    """Map a model ID to a prompt family folder name."""
    model_lower = model_id.lower()
    if "claude" in model_lower:
        return "claude"
    return "defaults"


def _load_module(family: str, stage: str):
    """Dynamically import app.prompts.<family>.<stage>"""
    try:
        return importlib.import_module(f"app.prompts.{family}.{stage}")
    except ModuleNotFoundError:
        if family != "defaults":
            return importlib.import_module(f"app.prompts.defaults.{stage}")
        raise


def resolve_outline(
    *,
    model_id: str,
    title: str,
    notes_before: str,
    notes_after: str = "",
    previous_outline: str = "",
    user_override: str | None = None,
) -> dict[str, str]:
    if user_override:
        # User override is a raw system prompt string — use default user message structure
        mod = _load_module("defaults", "outline")
        result = mod.get(title, notes_before, notes_after, previous_outline)
        return {"system": user_override, "user": result["user"]}

    family = _family(model_id)
    mod = _load_module(family, "outline")
    return mod.get(title, notes_before, notes_after, previous_outline)


def resolve_chapter(
    *,
    model_id: str,
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    chapter_notes: str = "",
    user_override: str | None = None,
) -> dict[str, str]:
    family = _family(model_id)
    mod = _load_module(family, "chapter")
    result = mod.get(
        book_title=book_title,
        outline=outline,
        chapter_title=chapter_title,
        chapter_number=chapter_number,
        previous_summaries=previous_summaries,
        chapter_notes=chapter_notes,
    )
    if user_override:
        result["system"] = user_override
    return result


def resolve_chapter_revision(
    *,
    model_id: str,
    book_title: str,
    outline: str,
    chapter_title: str,
    chapter_number: int,
    previous_summaries: list[dict],
    original_content: str,
    editor_notes: str,
    user_override: str | None = None,
) -> dict[str, str]:
    family = _family(model_id)
    mod = _load_module(family, "chapter_revision")
    result = mod.get(
        book_title=book_title,
        outline=outline,
        chapter_title=chapter_title,
        chapter_number=chapter_number,
        previous_summaries=previous_summaries,
        original_content=original_content,
        editor_notes=editor_notes,
    )
    if user_override:
        result["system"] = user_override
    return result


def resolve_summary(
    *,
    model_id: str,
    chapter_content: str,
    chapter_number: int,
    chapter_title: str,
    user_override: str | None = None,
) -> dict[str, str]:
    family = _family(model_id)
    mod = _load_module(family, "summary")
    result = mod.get(
        chapter_content=chapter_content,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
    )
    if user_override:
        result["system"] = user_override
    return result
