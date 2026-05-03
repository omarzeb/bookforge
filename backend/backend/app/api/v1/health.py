"""
Health and readiness endpoints.

/health  — lightweight liveness check (no dependencies). Used by load balancers.
/ready   — full readiness check (DB + Redis). Used by App Runner as the health check.
"""

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness — always returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    """
    Readiness — checks DB and Redis connectivity.
    Returns 200 if both are reachable, 503 otherwise.
    App Runner uses this as its health check target.
    """
    checks: dict[str, str] = {}
    healthy = True

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("readiness_db_failed", error=str(exc))
        checks["db"] = "unavailable"
        healthy = False

    # Redis check
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("readiness_redis_failed", error=str(exc))
        checks["redis"] = "unavailable"
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
