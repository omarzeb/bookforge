from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

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
        import re as _re
        import sentry_sdk

        _SENSITIVE = _re.compile(
            r"(api_key|password|secret|token|authorization|cookie|fernet|jwt)",
            _re.IGNORECASE,
        )

        def _scrub_event(event, hint):
            """Strip auth headers and sensitive fields before sending to Sentry."""
            # Remove Authorization and Cookie headers
            try:
                headers = event.get("request", {}).get("headers", {})
                for h in list(headers.keys()):
                    if _SENSITIVE.search(h):
                        headers[h] = "[Filtered]"
            except Exception:
                pass
            # Redact sensitive keys in extra context
            try:
                for key in list(event.get("extra", {}).keys()):
                    if _SENSITIVE.search(key):
                        event["extra"][key] = "[Filtered]"
            except Exception:
                pass
            return event

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=settings.app_env.value,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.0,
            send_default_pii=False,   # never attach user IP, cookies, or PII
            before_send=_scrub_event,
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

    # CORS: never use allow_origins=["*"] with allow_credentials=True
    # (spec prohibits it). Read explicit origins from env.
    frontend_origin = getattr(settings, "frontend_origin", "http://localhost:3000")
    allowed_origins = [o.strip() for o in frontend_origin.split(",") if o.strip()]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Correlation-ID"],
    )

    # Rate limiting — Limiter is constructed with storage_uri in rate_limit.py
    from app.core.rate_limit import limiter, user_limiter
    application.state.limiter = limiter
    application.state.user_limiter = user_limiter
    application.add_middleware(SlowAPIMiddleware)
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
