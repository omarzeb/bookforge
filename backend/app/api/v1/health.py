"""
Health and readiness endpoints — updated for Phase 10.

/health  — liveness (no deps)
/ready   — DB + Redis + OpenRouter reachability
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
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    checks: dict[str, str] = {}
    healthy = True

    # DB
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("readiness_db_failed", error=str(exc))
        checks["db"] = "unavailable"
        healthy = False

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("readiness_redis_failed", error=str(exc))
        checks["redis"] = "unavailable"
        healthy = False

    # OpenRouter (lightweight — just a DNS/TCP check, no token burn)
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                timeout=5.0,
                headers={"Authorization": "Bearer test"},  # will 401 but proves reachability
            )
            checks["openrouter"] = "ok" if resp.status_code in (200, 401) else "degraded"
    except Exception as exc:
        logger.warning("readiness_openrouter_failed", error=str(exc))
        checks["openrouter"] = "unreachable"
        # Don't fail health for OpenRouter — it's external

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
