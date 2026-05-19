from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import close_db, init_db
from app.db.redis import close_redis, init_redis

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()

    # Init Sentry if DSN is configured
    sentry_dsn = getattr(settings, "sentry_dsn", "")
    if sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=settings.app_env.value,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.0,
        )
        logger.info("sentry_initialized")

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

    # Correlation ID must be first so all subsequent middleware/handlers get the ID
    application.add_middleware(CorrelationIdMiddleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    from app.api.v1.health        import router as health_router
    from app.api.v1.auth          import router as auth_router
    from app.api.v1.settings      import router as settings_router
    from app.api.v1.models        import router as models_router
    from app.api.v1.books         import router as books_router
    from app.api.v1.chapters      import router as chapters_router
    from app.api.v1.ingest        import router as ingest_router
    from app.api.v1.jobs          import router as jobs_router
    from app.api.v1.reconciliation import router as reconciliation_router
    from app.api.v1.prompts       import router as prompts_router
    from app.api.v1.cost          import router as cost_router
    from app.api.v1.usage         import router as usage_router

    application.include_router(health_router)
    application.include_router(auth_router,          prefix="/api/v1")
    application.include_router(settings_router,      prefix="/api/v1")
    application.include_router(models_router,        prefix="/api/v1")
    application.include_router(books_router,         prefix="/api/v1")
    application.include_router(chapters_router,      prefix="/api/v1")
    application.include_router(ingest_router,        prefix="/api/v1")
    application.include_router(jobs_router,          prefix="/api/v1")
    application.include_router(reconciliation_router,prefix="/api/v1")
    application.include_router(prompts_router,       prefix="/api/v1")
    application.include_router(cost_router,          prefix="/api/v1")
    application.include_router(usage_router,         prefix="/api/v1")

    return application


app = create_app()
