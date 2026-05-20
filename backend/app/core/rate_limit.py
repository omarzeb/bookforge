"""
Rate limiting via slowapi + Redis.

The Limiter must be constructed with storage_uri at import time.
Import this module AFTER settings are loaded.
"""
from app.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

def _get_redis_uri() -> str:
    """Use Redis if configured, fall back to in-memory for tests."""
    if settings.redis_url:
        return settings.redis_url
    return "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_get_redis_uri(),
    default_limits=["200/minute"],
)
