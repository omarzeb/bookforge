"""
Cost estimation endpoint.

GET /models/{model_id}/estimate?chapters=10
  Returns estimated cost range for generating a book with this model.
  Uses live pricing from ModelCache table.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import ModelCache, User
from app.db.session import get_db
from app.services.model_tiers import CURATED_MODELS, TIER_ORDER, estimate_book_cost, get_curated_model

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["models"])


class CuratedModelResponse(BaseModel):
    model_id: str
    name: str
    tier: str
    context_k: int
    notes: str
    prompt_price_per_1k: float | None = None
    completion_price_per_1k: float | None = None
    model_config = {"from_attributes": True, "protected_namespaces": ()}


class CostEstimateResponse(BaseModel):
    model_id: str
    chapters: int
    low_usd: float | None
    high_usd: float | None
    note: str = ""
    model_config = {"from_attributes": True, "protected_namespaces": ()}


@router.get("/models/curated", response_model=list[CuratedModelResponse])
async def list_curated_models(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CuratedModelResponse]:
    """
    Return the curated model list with live pricing from ModelCache.
    This is what the ModelDropdown component in the frontend uses.
    """
    result = await db.execute(select(ModelCache))
    cache = {m.model_id: m for m in result.scalars().all()}

    models = []
    for cm in sorted(CURATED_MODELS, key=lambda m: TIER_ORDER.get(m.tier, 99)):
        cached = cache.get(cm.model_id)
        models.append(CuratedModelResponse(
            model_id=cm.model_id,
            name=cm.name,
            tier=cm.tier,
            context_k=cm.context_k,
            notes=cm.notes,
            prompt_price_per_1k=cached.prompt_price_per_1k if cached else None,
            completion_price_per_1k=cached.completion_price_per_1k if cached else None,
        ))

    return models


@router.get("/models/estimate", response_model=CostEstimateResponse)
async def estimate_cost(
    model_id: str,
    chapters: int = 10,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CostEstimateResponse:
    """
    Estimate the cost to generate a book with the given model.
    Used by the CostEstimate component in the frontend.
    """
    if chapters < 1 or chapters > 50:
        raise HTTPException(status_code=422, detail="chapters must be between 1 and 50")

    result = await db.execute(
        select(ModelCache).where(ModelCache.model_id == model_id)
    )
    cached = result.scalar_one_or_none()

    estimate = estimate_book_cost(
        chapters=chapters,
        prompt_price_per_1k=cached.prompt_price_per_1k if cached else None,
        completion_price_per_1k=cached.completion_price_per_1k if cached else None,
    )

    note = ""
    if estimate["low"] is None:
        note = "Pricing not available — sync the model list first"
    elif estimate["high"] and estimate["high"] > 1.0:
        note = "Consider a Budget tier model for long books"

    return CostEstimateResponse(
        model_id=model_id,
        chapters=chapters,
        low_usd=estimate["low"],
        high_usd=estimate["high"],
        note=note,
    )
