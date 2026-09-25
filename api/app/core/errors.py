"""The error envelope and the handlers that produce it.

Every non-2xx response has exactly this shape (`02-ARCHITECTURE.md` §3):

    {"error": {"code": "INSUFFICIENT_CREDITS",
               "message": "You need 5 credits.",
               "details": {"required": 5, "balance": 2}}}

Codes come from the table in `04-API.md` — never invent one at a call site.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger(__name__)

# Status codes FastAPI/Starlette raise on their own, mapped onto our codes so a
# framework 404 or 405 looks like every other error to a client.
_STATUS_TO_CODE: dict[int, str] = {
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "NOT_FOUND",
    429: "RATE_LIMITED",
}


class AppError(Exception):
    """A deliberate, client-facing failure.

    `message` is shown to the user, so it must never contain internals,
    identifiers of other users, or anything from rule 15's never-log list.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def envelope(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status,
        content=envelope(exc.code, exc.message, exc.details),
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [
        {
            "field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][0]),
            "problem": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content=envelope(
            "VALIDATION_ERROR",
            "Some of the information sent was not valid.",
            {"fields": fields},
        ),
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_TO_CODE.get(exc.status_code, "INTERNAL")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    if code == "NOT_FOUND":
        message = "Not found."
    return JSONResponse(status_code=exc.status_code, content=envelope(code, message))


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log with the request id, tell the client nothing.

    T-9.12 adds Sentry here; the exception is already bound to the request id by
    the logging middleware, so reporting is a one-line addition.
    """
    log.exception("unhandled_exception", exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=envelope("INTERNAL", "Something went wrong on our end."),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
