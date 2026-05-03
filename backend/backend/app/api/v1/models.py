"""
Models routes.

GET /models
  Returns the cached model list with tier labels.
  If the cache is empty, triggers a sync first.
"""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelCache
from app.db.session import get_db
from app.services.model_sync import sync_models

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/models", tags=["models"])


class ModelResponse(BaseModel):
    model_id: str
    name: str
    context_length: int | None
    prompt_price_per_1k: float | None
    completion_price_per_1k: float | None
    tier: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)) -> list[ModelCache]:
    """
    Return the cached model list grouped by tier.
    Triggers a sync if the cache is empty.
    """
    result = await db.execute(
        select(ModelCache)
        .where(ModelCache.is_active == True)  # noqa: E712
        .order_by(ModelCache.tier, ModelCache.name)
    )
    models = list(result.scalars().all())

    if not models:
        logger.info("model_cache_empty_syncing")
        await sync_models(db)
        result = await db.execute(
            select(ModelCache)
            .where(ModelCache.is_active == True)  # noqa: E712
            .order_by(ModelCache.tier, ModelCache.name)
        )
        models = list(result.scalars().all())

    return models
