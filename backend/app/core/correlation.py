"""
Correlation ID middleware.

Generates a unique request ID for every incoming HTTP request.
Injects it into structlog context so every log line for that request
includes the same correlation_id — making it trivial to trace a
user-reported issue across API → service → worker.

The ID is also returned in the X-Correlation-ID response header so
the frontend can include it in bug reports.
"""

import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Accept an incoming correlation ID (e.g. from a frontend retry)
        # or generate a fresh one
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER)
            or str(uuid.uuid4())[:16]
        )

        # Bind to structlog context — every log call in this request gets it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        # Echo it back so the frontend/client can log or display it
        response.headers[CORRELATION_ID_HEADER] = correlation_id

        # Log completed requests (skip health checks to reduce noise)
        if request.url.path not in ("/health", "/ready"):
            logger.info(
                "request_completed",
                status_code=response.status_code,
            )

        return response
