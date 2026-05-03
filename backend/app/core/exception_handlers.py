"""
Domain error → HTTP response mapping.

Add your domain exceptions here and map them to appropriate HTTP status codes.
This keeps HTTP concerns out of service layer code.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


# ── Domain exceptions ─────────────────────────────────────────────────────────

class BookForgeError(Exception):
    """Base class for all application errors."""


class NotFoundError(BookForgeError):
    """Resource does not exist or belongs to a different user."""


class ForbiddenError(BookForgeError):
    """Authenticated user is not allowed to access this resource."""


class ValidationError(BookForgeError):
    """Input failed business-rule validation (distinct from Pydantic validation)."""


class ConflictError(BookForgeError):
    """Operation is not valid given current resource state."""


class ProviderError(BookForgeError):
    """LLM provider returned an error (base class — see providers/exceptions.py)."""


# ── Handler registration ──────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc) or "Not found"})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc) or "Forbidden"})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def provider_handler(request: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(BookForgeError)
    async def generic_handler(request: Request, exc: BookForgeError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
