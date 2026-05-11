"""
Usage logging service.

Called after every LLM generation to record spend.
This powers the per-user usage dashboard.
"""

import time
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageLog

logger = structlog.get_logger(__name__)


async def log_usage(
    db: AsyncSession,
    *,
    user_id: str,
    book_id: str | None,
    model: str,
    stage: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    duration_ms: int,
) -> UsageLog:
    """Record a single LLM call. Call this after every generate() call."""
    entry = UsageLog(
        user_id=user_id,
        book_id=book_id,
        model=model,
        stage=stage,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        created_at=datetime.utcnow(),
    )
    db.add(entry)

    logger.info(
        "llm_usage",
        user_id=user_id,
        model=model,
        stage=stage,
        tokens=prompt_tokens + completion_tokens,
        cost_usd=round(cost_usd, 6),
        duration_ms=duration_ms,
    )
    return entry


async def get_usage_summary(
    db: AsyncSession,
    user_id: str,
    days: int = 30,
) -> dict:
    """Return usage summary for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.user_id == user_id, UsageLog.created_at >= since)
        .order_by(UsageLog.created_at.desc())
        .limit(200)
    )
    logs = result.scalars().all()

    total_cost = sum(l.cost_usd for l in logs)
    total_tokens = sum(l.prompt_tokens + l.completion_tokens for l in logs)

    # Group by model
    by_model: dict[str, dict] = {}
    for l in logs:
        if l.model not in by_model:
            by_model[l.model] = {"cost_usd": 0.0, "calls": 0, "tokens": 0}
        by_model[l.model]["cost_usd"] += l.cost_usd
        by_model[l.model]["calls"] += 1
        by_model[l.model]["tokens"] += l.prompt_tokens + l.completion_tokens

    return {
        "period_days": days,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "total_calls": len(logs),
        "by_model": [
            {
                "model": model,
                "cost_usd": round(v["cost_usd"], 6),
                "calls": v["calls"],
                "tokens": v["tokens"],
            }
            for model, v in sorted(
                by_model.items(), key=lambda x: x[1]["cost_usd"], reverse=True
            )
        ],
        "recent": [
            {
                "id": l.id,
                "model": l.model,
                "stage": l.stage,
                "prompt_tokens": l.prompt_tokens,
                "completion_tokens": l.completion_tokens,
                "cost_usd": l.cost_usd,
                "duration_ms": l.duration_ms,
                "created_at": l.created_at.isoformat(),
                "book_id": l.book_id,
            }
            for l in logs[:50]
        ],
    }
