"""
Usage logging service.

Called after every LLM generation to record spend.
This powers the per-user usage dashboard.
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
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
        created_at=datetime.now(UTC),
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
    since = datetime.now(UTC) - timedelta(days=days)

    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.user_id == user_id, UsageLog.created_at >= since)
        .order_by(UsageLog.created_at.desc())
        .limit(200)
    )
    logs = result.scalars().all()

    total_cost = sum(entry.cost_usd for entry in logs)
    total_tokens = sum(entry.prompt_tokens + entry.completion_tokens for entry in logs)

    # Group by model
    by_model: dict[str, dict] = {}
    for entry in logs:
        if entry.model not in by_model:
            by_model[entry.model] = {"cost_usd": 0.0, "calls": 0, "tokens": 0}
        by_model[entry.model]["cost_usd"] += entry.cost_usd
        by_model[entry.model]["calls"] += 1
        by_model[entry.model]["tokens"] += entry.prompt_tokens + entry.completion_tokens

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
                "model": entry.model,
                "stage": entry.stage,
                "prompt_tokens": entry.prompt_tokens,
                "completion_tokens": entry.completion_tokens,
                "cost_usd": entry.cost_usd,
                "duration_ms": entry.duration_ms,
                "created_at": entry.created_at.isoformat(),
                "book_id": entry.book_id,
            }
            for entry in logs[:50]
        ],
    }
