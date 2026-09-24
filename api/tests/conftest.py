"""Minimal fixtures for T-1.3.

T-1.5 owns the real harness — migrated test database, per-test transaction
rollback, `make_user`, fake providers. Everything here is only what this task's
tests need, and is expected to be absorbed into that work.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

# Settings are read at import time, so the environment must exist before any
# application module is imported.
_TEST_ENV = {
    "ENV": "local",
    "DATABASE_URL": "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora_test",
    "REDIS_URL": "redis://127.0.0.1:6379/1",
    "JWT_SECRET": "test-secret-not-a-real-key",
    "PHONE_PEPPER": "test-pepper",
    "PHONE_ENC_KEY": "test-enc-key",
    "CORS_ORIGINS": "http://localhost:3000",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture
def app_settings() -> Iterator[None]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """An HTTP client bound to the app, without going over the network."""
    from app.main import close_resources, create_app

    application = create_app()
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        # The in-process transport does not run the lifespan, so close here.
        await close_resources(application)
