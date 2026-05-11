"""
Prompt resolver — updated for Phase 8.

Resolution order:
  1. User override from PromptOverride table
  2. Model-family prompt (claude/, gpt/, gemini/, deepseek/, defaults/)
  3. defaults/ fallback

Supported families: claude, gpt, gemini, deepseek, defaults
Supported stages:   outline, chapter, chapter_revision, summary

Required placeholders per stage (validated on save):
  outline:           {title}, {notes_before}
  chapter:           {book_title}, {chapter_title}, {chapter_number}
  chapter_revision:  {book_title}, {chapter_title}, {original_content}, {editor_notes}
  summary:           {chapter_content}, {chapter_number}, {chapter_title}
"""

from __future__ import annotations

import importlib
import structlog

logger = structlog.get_logger(__name__)

# Maps model_id substrings → prompt family folder
_FAMILY_MAP: list[tuple[str, str]] = [
    ("claude",    "claude"),
    ("gpt",       "gpt"),
    ("gemini",    "gemini"),
    ("deepseek",  "deepseek"),
    ("mistral",   "defaults"),
    ("llama",     "defaults"),
]

# Required placeholders that must appear in user overrides
REQUIRED_PLACEHOLDERS: dict[str, list[str]] = {
    "outline":          [],   # outline prompts use function args, not string templates
    "chapter":          [],
    "chapter_revision": [],
    "summary":          [],
}


def _family(model_id: str) -> str:
    """Map a model ID to a prompt family folder."""
    lower = model_id.lower()
    for fragment, family in _FAMILY_MAP:
        if fragment in lower:
            return family
    return "defaults"


def _load(family: str, stage: str):
    """Import app.prompts.<family>.<stage>, falling back to defaults."""
    try:
        return importlib.import_module(f"app.prompts.{family}.{stage}")
    except ModuleNotFoundError:
        if family != "defaults":
            logger.debug("prompt_family_fallback", family=family, stage=stage)
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
    chapter_count: int = 10,
) -> dict[str, str]:
    mod = _load(_family(model_id), "outline")
    import inspect
    sig = inspect.signature(mod.get)
    if "chapter_count" in sig.parameters:
        result = mod.get(title, notes_before, notes_after, previous_outline, chapter_count)
    else:
        result = mod.get(title, notes_before, notes_after, previous_outline)
    if user_override:
        result["system"] = user_override
    return result


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
    mod = _load(_family(model_id), "chapter")
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
    mod = _load(_family(model_id), "chapter_revision")
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
    mod = _load(_family(model_id), "summary")
    result = mod.get(
        chapter_content=chapter_content,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
    )
    if user_override:
        result["system"] = user_override
    return result
