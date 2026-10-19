"""Structured logging and the request id that ties a request's lines together.

Logs are JSON in every deployed environment and human-readable locally. Every
line carries `request_id`, so one request can be followed end to end.

Every line at error level, and the warnings that are alerts, also goes to
Sentry where it is on (`core/observability.py`, T-9.12): what a line says is
what Sentry is told.

Rule 15: never log phone numbers, OTPs, tokens or message bodies. That is a
discipline at each call site — this module cannot enforce it, so review for it.
"""

from __future__ import annotations

import logging
import sys
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability import report_to_sentry

REQUEST_ID_HEADER = "X-Request-ID"


# One processor list for the life of the process, changed in place. structlog
# binds each logger, at first use, to the list configured then; with a new list
# per call (create_app() calls this every time), a logger used before the last
# call kept the old one, out of reach of structlog.testing.capture_logs, which
# edits the current list in place. A rule-15 test then passed having captured
# nothing (P-48).
_PROCESSORS: list[structlog.types.Processor] = []


def configure_logging(*, json_logs: bool, level: str = "INFO") -> None:
    """Configure structlog and route the stdlib logger through it."""
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        # Before the exception is formatted into text: it reads exc_info itself.
        report_to_sentry,
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    _PROCESSORS[:] = [*shared, renderer]
    structlog.configure(
        processors=_PROCESSORS,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level]
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Uvicorn and SQLAlchemy log through the stdlib; send them to the same sink.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    for name in _UVICORN_REQUEST_LINES:
        logger = logging.getLogger(name)
        if _NO_QUERY not in logger.filters:
            logger.addFilter(_NO_QUERY)


class _PathsWithoutQuery(logging.Filter):
    """Uvicorn writes each request's path with its query: an HTTP request's on
    `uvicorn.access`, a socket's (`"WebSocket /ws?ticket=…" [accepted]`) on
    `uvicorn.error`. The socket's ticket is the one secret a URL carries by
    design (T-7.4), so rule 15 keeps every query out of these lines (T-9.13,
    P-780). A logger's own filters outlive uvicorn's dictConfig."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                arg.split("?", 1)[0]
                if isinstance(arg, str) and arg.startswith("/")
                else arg
                for arg in record.args
            )
        return True


_UVICORN_REQUEST_LINES = ("uvicorn.access", "uvicorn.error")
_NO_QUERY = _PathsWithoutQuery()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Give every request an id, bind it to the logger, echo it back.

    An inbound `X-Request-ID` is trusted and reused so a trace survives across
    services; otherwise one is generated.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("method", "path")

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
