"""Error Handler module."""

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("antigravity_k.api.errors")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler to prevent the API from crashing.

    and returning unstructured HTML traces to clients.
    """
    error_msg = str(exc)
    tb_str = traceback.format_exc()

    logger.error(
        "Unhandled exception caught on %s %s: %s\n%s",
        request.method,
        request.url,
        error_msg,
        tb_str,
    )

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "Internal Server Error",
            "detail": error_msg,
            "path": str(request.url.path),
        },
    )
