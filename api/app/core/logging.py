"""Structured logging and the request id that ties a request's lines together.

Logs are JSON in every deployed environment and human-readable locally. Every
line carries `request_id`, so one request can be followed end to end.

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

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(*, json_logs: bool, level: str = "INFO") -> None:
    """Configure structlog and route the stdlib logger through it."""
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level]
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Uvicorn and SQLAlchemy log through the stdlib; send them to the same sink.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)


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
