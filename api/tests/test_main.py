"""`create_app(settings)` must be authoritative for everything it builds.

Regression for P-05: the database and Redis connections used to come from the
global `get_settings()`, so settings passed to `create_app` configured CORS and
logging but not the connections — a harness passing test settings would have
run against the dev database.
"""

from __future__ import annotations

from app.core.config import Settings
from app.main import close_resources, create_app


def _settings(database: str, redis_db: int) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ENV="local",
        DATABASE_URL=f"postgresql+asyncpg://velora:velora@127.0.0.1:5432/{database}",
        REDIS_URL=f"redis://127.0.0.1:6379/{redis_db}",
        JWT_SECRET="x",
        PHONE_PEPPER="x",
        PHONE_ENC_KEY="x",
    )


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
