"""
Model cache sync service.

Calls OpenRouter's /models endpoint and writes results to the ModelCache table.
Called on startup and periodically to keep the model list fresh.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ModelCache
from app.providers.openrouter import OpenRouterProvider

logger = structlog.get_logger(__name__)

# Models we curate into tiers. Everything else goes into "Other".
_RECOMMENDED = {
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
}

_BUDGET = {
    "mistralai/mistral-7b-instruct",
    "meta-llama/llama-3-8b-instruct",
    "google/gemma-2-9b-it",
}

_PREMIUM = {
    "anthropic/claude-3-opus",
    "openai/gpt-4-turbo",
    "google/gemini-pro-1.5",
}


def _assign_tier(model_id: str) -> str:
    if model_id in _RECOMMENDED:
        return "Recommended"
    if model_id in _PREMIUM:
        return "Premium"
    if model_id in _BUDGET:
        return "Budget"
    return "Other"


async def sync_models(db: AsyncSession) -> int:
    """
    Fetch live models from OpenRouter and upsert into ModelCache.
    Returns the number of models synced.
    Requires either a demo key or any valid user key — uses demo key here
    since this runs as a background service task.
    """
    api_key = settings.openrouter_demo_key
    if not api_key:
        logger.warning("model_sync_skipped", reason="no demo key configured")
        return 0

    provider = OpenRouterProvider(api_key=api_key)

    try:
        models = await provider.list_models()
    except Exception as exc:
        logger.error("model_sync_failed", error=str(exc))
        return 0

    synced = 0
    for m in models:
        if not m.model_id:
            continue

        # Upsert: update if exists, insert if not
        result = await db.execute(
            select(ModelCache).where(ModelCache.model_id == m.model_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = m.name
            existing.context_length = m.context_length
            existing.prompt_price_per_1k = m.prompt_price_per_1k
            existing.completion_price_per_1k = m.completion_price_per_1k
            existing.tier = _assign_tier(m.model_id)
            existing.is_active = True
        else:
            db.add(ModelCache(
                model_id=m.model_id,
                name=m.name,
                context_length=m.context_length,
                prompt_price_per_1k=m.prompt_price_per_1k,
                completion_price_per_1k=m.completion_price_per_1k,
                tier=_assign_tier(m.model_id),
                is_active=True,
            ))

        synced += 1

    await db.commit()
    logger.info("model_sync_complete", count=synced)
    return synced
