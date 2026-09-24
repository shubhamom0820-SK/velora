"""FastAPI application factory.

`create_app()` builds a fully configured app; the module-level `app` exists so
`uvicorn app.main:app` works. Routers are mounted here as modules land — the
factory is the only place that knows the whole app.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestIDMiddleware, configure_logging

APP_NAME = "Velora"  # One constant, so a rename stays cheap (D-015).


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    configure_logging(json_logs=not settings.debug)

    app = FastAPI(
        title=f"{APP_NAME} API",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # Outermost middleware runs first: everything downstream, handlers included,
    # logs with the request id already bound.
    app.add_middleware(RequestIDMiddleware)

    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    register_error_handlers(app)

    return app


app = create_app()
