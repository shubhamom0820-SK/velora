"""FastAPI application factory.

`create_app()` builds a fully configured app; the module-level `app` exists so
`uvicorn app.main:app` works. Routers are mounted here as modules land — the
factory is the only place that knows the whole app.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_sessionmaker
from app.core.errors import register_error_handlers
from app.core.headers import SecurityHeadersMiddleware
from app.core.logging import RequestIDMiddleware, configure_logging
from app.core.providers import build_providers
from app.core.redis import build_redis
from app.modules.auth.router import otp_router
from app.modules.health.router import router as health_router
from app.modules.waitlist.router import router as waitlist_router

APP_NAME = "Velora"  # One constant, so a rename stays cheap (D-015).
SCHEMA_SERVED_IN: frozenset[str] = frozenset({"local"})
# Path B's sign-in routes (/v1/auth/otp/*) are served only for these providers:
# an allowlist (rule 16, D-066). Everywhere else they 404, so staging and
# production, on firebase, can't be made to send a Path B SMS at all.
OTP_SERVED_FOR: frozenset[str] = frozenset({"msg91", "fake"})


async def close_resources(app: FastAPI) -> None:
    """Release this app's connections. Safe to call more than once.

    The lifespan calls it on shutdown; tests call it directly, because an
    in-process test client does not run the lifespan.
    """
    await app.state.redis.aclose()
    await app.state.engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_resources(app)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    configure_logging(json_logs=not settings.debug)

    # The schema and Swagger UI are served only where ENV is local: an allowlist
    # (rule 16), since a public schema of the wallet, payment and admin routes is
    # free reconnaissance (P-31). Nothing needs them elsewhere — `make types`
    # generates from `app.openapi()` offline (D-043).
    serve_schema = settings.ENV in SCHEMA_SERVED_IN
    app = FastAPI(
        title=f"{APP_NAME} API",
        version="0.1.0",
        docs_url="/docs" if serve_schema else None,
        redoc_url=None,
        openapi_url="/openapi.json" if serve_schema else None,
        lifespan=lifespan,
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

    # nosniff everywhere and no-store on /v1 (P-42). Added last, so it is the
    # outermost: it sees every response, CORS's own preflight answers included.
    app.add_middleware(SecurityHeadersMiddleware)

    register_error_handlers(app)

    # Connections come from *these* settings, never the global ones, so an app
    # built for tests cannot reach the dev database (P-05). Nothing connects
    # yet: startup succeeds with a dependency down, and /readyz reports it.
    app.state.settings = settings
    app.state.engine = build_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )
    app.state.sessionmaker = build_sessionmaker(app.state.engine)
    app.state.redis = build_redis(settings.REDIS_URL)
    # External services (D-028): fakes locally and in tests, real ones elsewhere.
    app.state.providers = build_providers(settings)

    # Probes at the root, unversioned; product routers go under /v1.
    app.include_router(health_router)
    app.include_router(waitlist_router, prefix="/v1")
    if settings.AUTH_PHONE_PROVIDER in OTP_SERVED_FOR:
        app.include_router(otp_router, prefix="/v1")

    return app


app = create_app()
