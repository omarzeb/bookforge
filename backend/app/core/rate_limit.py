"""
Rate limiting via slowapi + Redis.

Two key functions:
- get_remote_address  — IP-based (used for auth endpoints)
- get_user_id         — user-ID-based (used for cost-incurring endpoints)

The Limiter must be constructed with storage_uri at import time.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_user_id(request) -> str:
    """
    Rate-limit key: authenticated user ID.
    Falls back to IP so unauthenticated requests are still throttled.
    A stolen token rotating IPs still hits the same per-user bucket.
    """
    # FastAPI attaches the current user to request.state after auth dependency runs.
    # For SlowAPI the key_func runs before the endpoint, so we decode the token here.
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt as pyjwt
            from app.config import settings
            payload = pyjwt.decode(
                auth[7:],
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                audience="bookforge-api",
                issuer="bookforge",
            )
            return f"user:{payload['sub']}"
        except Exception:
            pass
    return get_remote_address(request)


def _get_redis_uri() -> str:
    try:
        from app.config import settings
        return settings.redis_url or "memory://"
    except Exception:
        return "memory://"


# IP-keyed limiter — for auth endpoints
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_get_redis_uri(),
    default_limits=["200/minute"],
)

# User-ID-keyed limiter — for cost-incurring endpoints
user_limiter = Limiter(
    key_func=get_user_id,
    storage_uri=_get_redis_uri(),
)
