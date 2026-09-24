"""`get_session` yields a live session on the app's own database."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.main import close_resources, create_app
from tests.infra import requires_infra

_TEST_DB_URL = "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora_test"
_DEV_DB_URL = "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora"


@pytest.fixture
def global_settings_point_at_dev(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make the process-wide settings disagree with the app's, as they would
    for a developer whose shell exports their dev DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", _DEV_DB_URL)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@requires_infra
async def test_get_session_uses_the_apps_database_not_the_global_one(
    global_settings_point_at_dev: None,
) -> None:
    assert get_settings().DATABASE_URL == _DEV_DB_URL  # the trap is set

    app = create_app(
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            ENV="local",
            DATABASE_URL=_TEST_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/1",
            JWT_SECRET="x",
            PHONE_PEPPER="x",
            PHONE_ENC_KEY="x",
        )
    )

    @app.get("/v1/_test/current-database")
    async def _current_database(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str]:
        result = await session.execute(text("select current_database()"))
        return {"database": result.scalar_one()}

    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/_test/current-database")
    finally:
        await close_resources(app)

    assert response.status_code == 200
    assert response.json() == {"database": "velora_test"}
