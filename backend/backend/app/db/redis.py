"""
Redis client management.

Usage in FastAPI routes:
    async def my_route(redis: Redis = Depends(get_redis)):
        await redis.set("key", "value")
"""

from collections.abc import AsyncGenerator

import structlog
from redis.asyncio import Redis

from app.config import settings

logger = structlog.get_logger(__name__)

_redis: Redis | None = None


async def init_redis() -> None:
    """Create the Redis client. Called at app startup."""
    global _redis
    _redis = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    # Verify connectivity immediately
    await _redis.ping()
    logger.info("redis_connected")


async def close_redis() -> None:
    """Close the Redis connection. Called at app shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        logger.info("redis_disconnected")


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency that yields the shared Redis client."""
    if _redis is None:
        raise RuntimeError("Redis not initialised — call init_redis() first")
    yield _redis
