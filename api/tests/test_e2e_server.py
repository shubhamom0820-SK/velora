"""The E2E server's client addresses (P-680, D-890): each browser context is a
client of its own, read from a header only ENV local may read."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import ModuleType

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import FakeProviders
from tests.e2e_server import E2E_CLIENT_IP_HEADER, e2e_settings, shared_settings
from tests.infra import API_DIR

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 9, 6, 30, tzinfo=UTC)
SEND = "/v1/auth/otp/send"
FIXTURES = API_DIR.parent / "web" / "e2e" / "fixtures.ts"


def test_the_e2e_server_reads_each_contexts_header_and_is_local() -> None:
    settings = e2e_settings(shared_settings())

    assert settings.ENV == "local"
    assert settings.CLIENT_IP_HEADER == "X-E2E-Client-IP"


def test_the_web_fixtures_send_the_header_the_server_reads() -> None:
    """The two sides name one header. Drifted apart, every context would share
    the header-less bucket, and the suite would fail at someone's 21st send."""
    assert f'"{E2E_CLIENT_IP_HEADER}"' in FIXTURES.read_text()


@pytest.fixture
async def e2e_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """The test app reading the client's address as the E2E server does."""
    header = e2e_settings(shared_settings()).CLIENT_IP_HEADER
    app.state.settings = app.state.settings.model_copy(
        update={"CLIENT_IP_HEADER": header}
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_each_context_has_d066s_twenty_sends_of_its_own(
    db: AsyncSession,
    e2e_client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """Every request reaches the E2E server from 127.0.0.1; the header, not the
    socket, decides whose 20 sends an hour a send counts against."""
    clock.freeze(START)

    async def send(i: int, address: str) -> int:
        response = await e2e_client.post(
            SEND,
            json={"phone": f"+9198765{i:05d}"},
            headers={E2E_CLIENT_IP_HEADER: address},
        )
        if response.status_code == 429:
            assert response.json()["error"]["code"] == "RATE_LIMITED"
        return response.status_code

    for i in range(20):
        assert await send(i, "198.18.0.1") == 200

    assert await send(20, "198.18.0.1") == 429
    assert await send(21, "198.18.0.2") == 200
    assert len(fake_providers.sms.sent) == 21
