"""
Usage API — per-user spend and call history.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.usage_service import get_usage_summary

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return usage summary and recent call history for the authenticated user."""
    return await get_usage_summary(db, user.id, days=days)
