"""
Usage API — per-user spend and call history.
"""


import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.usage_service import get_usage_summary

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/usage", tags=["usage"])


class ModelStat(BaseModel):
    model: str
    cost_usd: float
    calls: int
    tokens: int


class RecentEntry(BaseModel):
    id: str
    model: str
    stage: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    duration_ms: int
    created_at: str
    book_id: str | None


class UsageSummary(BaseModel):
    period_days: int
    total_cost_usd: float
    total_tokens: int
    total_calls: int
    by_model: list[ModelStat]
    recent: list[RecentEntry]


@router.get("", response_model=UsageSummary)
async def get_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UsageSummary:
    """Return usage summary and recent call history for the authenticated user."""
    data = await get_usage_summary(db, user.id, days=days)
    return UsageSummary(**data)
