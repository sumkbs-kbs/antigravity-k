"""Global exception handler and request-correlation-ID support.

Prevents raw exception details (``str(exc)``) from leaking to API clients.
Instead, every 500 response carries an opaque ``correlation_id`` that is also
logged server-side, so an operator can locate the full traceback in logs
without exposing internals to the caller.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from contextvars import ContextVar

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("antigravity_k.api.errors")

# ContextVar holding the current request's correlation id. Set by the
# correlation-id middleware (registered in server.py) and read by log filters.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler.

    Logs the full traceback server-side (keyed by a correlation id) and returns
    a generic 500 to the client with **no** internal detail exposed — only the
    correlation id, which the client can quote when reporting the issue.
    """
    # Prefer an existing correlation id from the request middleware; generate
    # one if the middleware did not set it (e.g. an error very early in the
    # request lifecycle).
    cid = correlation_id_var.get("") or uuid.uuid4().hex[:12]
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
            "error": "Internal Server Error",
            # Deliberately do NOT include str(exc) — it can leak paths, SQL,
            # or internal state. The correlation_id lets support find the log.
            "correlation_id": cid,
            "path": str(request.url.path),
        },
    )
