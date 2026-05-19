"""
Reconciliation endpoint — called by EventBridge every hour.

Marks RUNNING jobs that have been stuck longer than the timeout as FAILED.
This is a defensive measure for crashed Fargate tasks that never wrote back.

In production, EventBridge POSTs to this endpoint on a schedule.
The endpoint is protected by a shared secret so it's not publicly callable.
"""

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.task_launcher import reconcile_stuck_jobs

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])


class ReconcileResponse(BaseModel):
    stuck_jobs_marked_failed: int


@router.post("/reconcile", response_model=ReconcileResponse)
async def reconcile(
    x_internal_secret: str = Header(..., alias="X-Internal-Secret"),
    timeout_minutes: int = 30,
    db: AsyncSession = Depends(get_db),
) -> ReconcileResponse:
    """
    Mark stuck RUNNING jobs as FAILED.
    Protected by X-Internal-Secret header — set the same value in
    EventBridge and in APP_INTERNAL_SECRET env var.
    """
    import hmac as _hmac
    expected = getattr(settings, "app_internal_secret", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Internal secret not configured")
    if not _hmac.compare_digest(x_internal_secret, expected):
        raise HTTPException(status_code=403, detail="Invalid internal secret")

    count = await reconcile_stuck_jobs(db, timeout_minutes=timeout_minutes)
    logger.info("reconciliation_triggered", stuck_count=count)
    return ReconcileResponse(stuck_jobs_marked_failed=count)
