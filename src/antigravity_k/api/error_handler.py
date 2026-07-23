"""
Global exception handler, structured exception hierarchy, and request-correlation-ID support.

Prevents raw exception details from leaking to API clients while providing
structured error responses with correlation IDs for debugging.

Exception Hierarchy:
- APIError (base)
  - ValidationError (400)
  - AuthenticationError (401)
  - AuthorizationError (403)
  - NotFoundError (404)
  - RateLimitError (429)
  - ResourceLimitError (429)
  - InternalError (500)
  - ServiceUnavailableError (503)
"""

from __future__ import annotations

import logging
import traceback
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("antigravity_k.api.errors")

# ContextVar holding the current request's correlation id. Set by the
# correlation-id middleware (registered in server.py) and read by log filters.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


# ─── Structured Exception Hierarchy ───────────────────────────────────────


class APIError(Exception):
    """Base class for all structured API errors."""

    status_code: int = 500
    error_code: str = "internal_error"
    detail: str = "An unexpected error occurred"

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or self.detail)
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.context = context or {}

    # 예약 키 — to_dict()의 최상위 키와 충돌 방지
    _RESERVED_KEYS: frozenset = frozenset({"ok", "error", "detail", "correlation_id"})

    def to_dict(self, correlation_id: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {
            "ok": False,
            "error": self.error_code,
            "detail": self.detail,
            "correlation_id": correlation_id,
        }
        # context 병합 시 예약 키는 무시 (충돌 방지)
        for key, value in self.context.items():
            if key not in self._RESERVED_KEYS:
                result[key] = value
        return result


class ValidationError(APIError):
    status_code: int = 400
    error_code: str = "validation_error"
    detail: str = "Request validation failed"


class AuthenticationError(APIError):
    status_code: int = 401
    error_code: str = "authentication_error"
    detail: str = "Authentication required"


class AuthorizationError(APIError):
    status_code: int = 403
    error_code: str = "authorization_error"
    detail: str = "Insufficient permissions"


class NotFoundError(APIError):
    status_code: int = 404
    error_code: str = "not_found"
    detail: str = "Resource not found"


class RateLimitError(APIError):
    status_code: int = 429
    error_code: str = "rate_limit_exceeded"
    detail: str = "Too many requests"


class ResourceLimitError(APIError):
    status_code: int = 429
    error_code: str = "resource_limit_exceeded"
    detail: str = "Resource limit exceeded"


class InternalError(APIError):
    status_code: int = 500
    error_code: str = "internal_error"
    detail: str = "Internal server error"


class ServiceUnavailableError(APIError):
    status_code: int = 503
    error_code: str = "service_unavailable"
    detail: str = "Service temporarily unavailable"


class ModelUnavailableError(APIError):
    status_code: int = 503
    error_code: str = "model_unavailable"
    detail: str = "Requested model is not available"


# ─── Exception Handlers ───────────────────────────────────────────────────


def _get_correlation_id() -> str:
    return correlation_id_var.get("") or uuid.uuid4().hex[:12]


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler with structured error response.

    Logs the full traceback server-side (keyed by a correlation id) and returns
    a generic 500 to the client with **no** internal detail exposed — only the
    correlation id, which the client can quote when reporting the issue.
    """
    cid = _get_correlation_id()

    # Handle our structured exceptions
    if isinstance(exc, APIError):
        tb_str = traceback.format_exc()
        logger.warning(
            "APIError [correlation_id=%s] on %s %s: [%s] %s",
            cid,
            request.method,
            request.url,
            exc.error_code,
            exc.detail,
        )
        if exc.status_code >= 500:
            logger.error("Traceback:\n%s", tb_str)
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(correlation_id=cid),
        )

    # Generic fallback for unhandled exceptions
    tb_str = traceback.format_exc()
    logger.error(
        "Unhandled exception [correlation_id=%s] on %s %s: %s\n%s",
        cid,
        request.method,
        request.url,
        type(exc).__name__,
        tb_str,
    )

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "internal_error",
            "detail": "Internal Server Error",
            "correlation_id": cid,
            "path": str(request.url.path),
        },
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle FastAPI HTTPException with structured response."""
    from fastapi import HTTPException

    if not isinstance(exc, HTTPException):
        return await global_exception_handler(request, exc)

    cid = _get_correlation_id()
    logger.warning(
        "HTTPException [correlation_id=%s] on %s %s: status=%s",
        cid,
        request.method,
        request.url,
        exc.status_code,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": f"http_{exc.status_code}",
            "detail": exc.detail,
            "correlation_id": cid,
        },
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic/FastAPI validation errors with structured field-level errors."""
    from fastapi.exceptions import RequestValidationError

    if not isinstance(exc, RequestValidationError):
        return await global_exception_handler(request, exc)

    cid = _get_correlation_id()
    errors = []
    for err in exc.errors():
        errors.append(
            {
                "field": " -> ".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )

    logger.warning(
        "ValidationError [correlation_id=%s] on %s %s: %d field errors",
        cid,
        request.method,
        request.url,
        len(errors),
    )

    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": "validation_error",
            "detail": "Request validation failed",
            "correlation_id": cid,
            "errors": errors,
        },
    )
