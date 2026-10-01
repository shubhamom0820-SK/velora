"""`create_app(settings)` must be authoritative for everything it builds.

Regression for P-05: the database and Redis connections used to come from the
global `get_settings()`, so settings passed to `create_app` configured CORS and
logging but not the connections — a harness passing test settings would have
run against the dev database.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import close_resources, create_app

# D-045: outside local, every provider must be a real one.
_REAL_PROVIDERS = {
    "AUTH_PHONE_PROVIDER": "firebase",
    "SMS_PROVIDER": "msg91",
    "PAYMENTS_PROVIDER": "razorpay",
    "MODERATION_PROVIDER": "sightengine",
    "FACEMATCH_PROVIDER": "rekognition",
    "STORAGE_PROVIDER": "s3",
    "PUSH_PROVIDER": "webpush",
}


def _settings(database: str, redis_db: int, **overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        **{
            "ENV": "local",
            "DATABASE_URL": f"postgresql+asyncpg://velora:velora@127.0.0.1:5432/{database}",
            "REDIS_URL": f"redis://127.0.0.1:6379/{redis_db}",
            "JWT_SECRET": "x",
            "PHONE_PEPPER": "x",
            "PHONE_ENC_KEY": "x",
            **overrides,
        },
    )


async def _get(settings: Settings, path: str) -> tuple[int, str]:
    app = create_app(settings)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(path)
        return response.status_code, response.text
    finally:
        await close_resources(app)


async def test_engine_is_built_from_the_settings_given() -> None:
    app = create_app(_settings("velora_test", 1))
    try:
        assert app.state.engine.url.database == "velora_test"
    finally:
        await close_resources(app)


async def test_redis_is_built_from_the_settings_given() -> None:
    app = create_app(_settings("velora_test", 3))
    try:
        assert app.state.redis.connection_pool.connection_kwargs["db"] == 3
    finally:
        await close_resources(app)


async def test_two_apps_do_not_share_connections() -> None:
    """No process-wide singleton: each app owns its own engine and client."""
    first = create_app(_settings("velora_test", 1))
    second = create_app(_settings("velora", 2))
    try:
        assert first.state.engine is not second.state.engine
        assert first.state.redis is not second.state.redis
        assert first.state.engine.url.database == "velora_test"
        assert second.state.engine.url.database == "velora"
    finally:
        await close_resources(first)
        await close_resources(second)


async def test_close_resources_is_safe_to_call_twice() -> None:
    app = create_app(_settings("velora_test", 1))

    await close_resources(app)
    await close_resources(app)


# --- P-31: the schema and Swagger UI are served only where ENV is local --------


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("path", ["/openapi.json", "/docs"])
async def test_schema_and_docs_are_not_served_outside_local(
    env: str, path: str
) -> None:
    status, body = await _get(
        _settings(
            "velora_test",
            1,
            ENV=env,
            REDIS_URL="rediss://default:x@redis.example:6379/0",
            **_REAL_PROVIDERS,
        ),
        path,
    )

    assert status == 404
    assert '"code":"NOT_FOUND"' in body
    # The 404 must not carry the schema, or the UI, in its body.
    assert '"paths"' not in body
    assert "swagger" not in body.lower()


async def test_local_serves_the_schema_and_docs() -> None:
    schema_status, schema = await _get(_settings("velora_test", 1), "/openapi.json")
    docs_status, docs = await _get(_settings("velora_test", 1), "/docs")

    assert schema_status == 200
    assert '"paths"' in schema and '"/healthz"' in schema
    assert docs_status == 200
    assert "swagger" in docs.lower()


# --- The pool is sized per process, deliberately (T-1.22) ---------------------


async def test_engine_pool_is_sized_by_the_settings() -> None:
    app = create_app(_settings("velora_test", 1, DB_POOL_SIZE=3, DB_MAX_OVERFLOW=1))
    try:
        pool = app.state.engine.pool
        assert pool.size() == 3
        assert pool._max_overflow == 1
    finally:
        await close_resources(app)
