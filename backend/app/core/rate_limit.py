"""
Rate limiting via slowapi + Redis.

Limits:
- Auth endpoints: 5/minute per IP (brute-force protection)
- Advance/revise: 10/minute per user (cost-incurring actions)
- Book creation: 20/day per user
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter backed by Redis (Upstash in prod, local Redis in dev)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=None,   # set dynamically in create_app()
    default_limits=["200/minute"],
)
