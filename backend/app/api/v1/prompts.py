"""
Prompts API — GET/PUT user prompt overrides per stage.

GET  /prompts              → list all overrides for current user
GET  /prompts/{stage}      → get override for a specific stage (or 404)
PUT  /prompts/{stage}      → save/update override (validates placeholders)
DELETE /prompts/{stage}    → remove override (resets to default)

GET  /prompts/defaults/{stage}  → get the default system prompt for a stage
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import PromptOverride, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/prompts", tags=["prompts"])

VALID_STAGES = {"outline", "chapter", "chapter_revision", "summary"}


class PromptOverrideResponse(BaseModel):
    stage: str
    prompt_text: str

    model_config = {"from_attributes": True}


class SavePromptRequest(BaseModel):
    prompt_text: str


def _validate_prompt(stage: str, prompt_text: str) -> None:
    """
    Validate that a user prompt override is usable.
    Raises HTTPException if validation fails.
    """
    if not prompt_text.strip():
        raise HTTPException(status_code=422, detail="Prompt text cannot be empty")

    if len(prompt_text) > 10_000:
        raise HTTPException(
            status_code=422,
            detail="Prompt text too long (max 10,000 characters)",
        )

    # Stage-specific minimum content checks
    if stage == "outline" and len(prompt_text.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="Outline prompt is too short to be useful",
        )

    if stage == "chapter" and len(prompt_text.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="Chapter prompt is too short to be useful",
        )


@router.get("", response_model=list[PromptOverrideResponse])
async def list_overrides(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PromptOverride]:
    result = await db.execute(
        select(PromptOverride).where(PromptOverride.user_id == user.id)
    )
    return list(result.scalars().all())


@router.get("/defaults/{stage}")
async def get_default_prompt(stage: str) -> dict:
    """Return the default system prompt for a stage (for display in the editor)."""
    if stage not in VALID_STAGES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown stage '{stage}'. Valid stages: {sorted(VALID_STAGES)}",
        )

    # Load the defaults family and return the system prompt
    try:
        import importlib
        mod = importlib.import_module(f"app.prompts.defaults.{stage}")

        # Call get() with dummy args to extract the system prompt
        dummy_args: dict = {
            "outline": dict(title="[title]", notes_before="[notes]"),
            "chapter": dict(
                book_title="[title]", outline="[outline]",
                chapter_title="[chapter]", chapter_number=1,
                previous_summaries=[],
            ),
            "chapter_revision": dict(
                book_title="[title]", outline="[outline]",
                chapter_title="[chapter]", chapter_number=1,
                previous_summaries=[], original_content="[content]",
                editor_notes="[notes]",
            ),
            "summary": dict(
                chapter_content="[content]", chapter_number=1,
                chapter_title="[chapter]",
            ),
        }

        result = mod.get(**dummy_args[stage])
        return {"stage": stage, "system_prompt": result["system"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{stage}", response_model=PromptOverrideResponse)
async def get_override(
    stage: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromptOverride:
    if stage not in VALID_STAGES:
        raise HTTPException(status_code=404, detail=f"Unknown stage '{stage}'")

    result = await db.execute(
        select(PromptOverride).where(
            PromptOverride.user_id == user.id,
            PromptOverride.stage == stage,
        )
    )
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(
            status_code=404,
            detail=f"No custom prompt set for stage '{stage}'",
        )
    return override


@router.put("/{stage}", response_model=PromptOverrideResponse)
async def save_override(
    stage: str,
    body: SavePromptRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromptOverride:
    if stage not in VALID_STAGES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown stage '{stage}'. Valid: {sorted(VALID_STAGES)}",
        )

    _validate_prompt(stage, body.prompt_text)

    result = await db.execute(
        select(PromptOverride).where(
            PromptOverride.user_id == user.id,
            PromptOverride.stage == stage,
        )
    )
    override = result.scalar_one_or_none()

    if override:
        override.prompt_text = body.prompt_text
    else:
        override = PromptOverride(
            user_id=user.id,
            stage=stage,
            prompt_text=body.prompt_text,
        )
        db.add(override)

    await db.commit()
    await db.refresh(override)
    logger.info("prompt_override_saved", user_id=user.id, stage=stage)
    return override


@router.delete("/{stage}", status_code=204)
async def delete_override(
    stage: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if stage not in VALID_STAGES:
        raise HTTPException(status_code=404, detail=f"Unknown stage '{stage}'")

    result = await db.execute(
        select(PromptOverride).where(
            PromptOverride.user_id == user.id,
            PromptOverride.stage == stage,
        )
    )
    override = result.scalar_one_or_none()
    if override:
        await db.delete(override)
        await db.commit()
        logger.info("prompt_override_deleted", user_id=user.id, stage=stage)
