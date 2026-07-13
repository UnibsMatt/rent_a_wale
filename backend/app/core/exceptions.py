"""Domain exceptions and their HTTP mapping.

Services raise domain exceptions; a single FastAPI handler translates them, so routers
never build error responses by hand and internals never leak to clients.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger("app")


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class AuthenticationError(DomainError):
    status_code = 401
    code = "authentication_failed"


class PermissionDeniedError(DomainError):
    status_code = 403
    code = "permission_denied"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(DomainError):
    status_code = 422
    code = "validation_failed"


class InsufficientCreditsError(DomainError):
    status_code = 402
    code = "insufficient_credits"


class QuotaExceededError(DomainError):
    status_code = 422
    code = "quota_exceeded"


class HostCapacityError(DomainError):
    status_code = 503
    code = "host_capacity_exceeded"


class RateLimitedError(DomainError):
    status_code = 429
    code = "rate_limited"


class ProviderError(DomainError):
    status_code = 502
    code = "provider_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, **(
                {"detail": exc.detail} if exc.detail else {}
            )}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=str(request.url.path))
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )
