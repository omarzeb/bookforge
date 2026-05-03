"""
SQLAlchemy async engine and session management.

Usage in FastAPI routes:
    async def my_route(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
"""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = structlog.get_logger(__name__)

# Module-level engine — created once at startup, reused for all requests.
_engine = None
_session_factory = None


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def init_db() -> None:
    """Create the async engine and session factory. Called at app startup."""
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,          # logs all SQL in debug mode
        pool_pre_ping=True,           # verify connections before use (important for Neon)
        pool_size=5,
        max_overflow=10,
    )

    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,       # avoids lazy-load errors after commit
        class_=AsyncSession,
    )

    logger.info("db_connected", url=_redact_url(settings.database_url))


async def close_db() -> None:
    """Dispose the engine. Called at app shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("db_disconnected")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.
    Commits on success, rolls back on exception, always closes.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised — call init_db() first")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _redact_url(url: str) -> str:
    """Remove password from URL before logging."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        redacted = parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}")
        return urlunparse(redacted)
    except Exception:
        return "***"
