"""
RQ queue setup.

Central place to get the queue instance.
Both the API (for enqueuing) and the worker (for processing) import from here.
"""

import redis as sync_redis
from rq import Queue

from app.config import settings

# RQ requires a synchronous Redis connection (not async)
# This is only used for job enqueueing and the worker — not for app caching
_redis_conn: sync_redis.Redis | None = None


def get_redis_conn() -> sync_redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = sync_redis.from_url(settings.redis_url, decode_responses=False)
    return _redis_conn


def get_queue(name: str = "default") -> Queue:
    """Return an RQ Queue connected to Redis."""
    return Queue(name, connection=get_redis_conn())


# Named queues — separate queues let you prioritise and monitor independently
QUEUE_DEFAULT = "default"
QUEUE_OUTLINES = "outlines"
QUEUE_CHAPTERS = "chapters"
QUEUE_COMPILE = "compile"
