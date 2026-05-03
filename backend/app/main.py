"""
FastAPI application factory.

Wires together: lifespan (DB + Redis startup/shutdown), middleware,
exception handlers, and API routers.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import close_db, init_db
from app.db.redis import close_redis, init_redis

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic."""
    configure_logging()
    logger.info("starting_up", env=settings.app_env, debug=settings.debug)

    await init_db()
    await init_redis()

    logger.info("startup_complete")
    yield

    logger.info("shutting_down")
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    application = FastAPI(
        title="BookForge API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Phase 8 will tighten this to the Vercel domain.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(application)

    # ── Routers ───────────────────────────────────────────────────────────────
    # Imported here to avoid circular imports at module load time.
    from app.api.v1.health import router as health_router  # noqa: PLC0415
    application.include_router(health_router)

    return application


app = create_app()
