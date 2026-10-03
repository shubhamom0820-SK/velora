"""The E2E's test-only endpoint (T-3.13): the code the fake SMS provider last
sent a number, served only where ENV is local and the SMS is the fake's."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.enums import BanKind
from app.core.providers import FakeProviders
from app.core.security import E164, hash_phone
from app.main import close_resources, create_app
from app.modules.auth.models import BannedIdentity
from tests.conftest import CapturedLogs, make_test_settings
from tests.infra import session_for_the_app

pytestmark = pytest.mark.usefixtures("test_redis")

PHONE = E164("+919812345671")
TYPED = "98123 45671"
LAST_CODE = "/v1/test/sms/last-code"


async def test_answers_with_the_code_the_fake_sent(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    sent = await client.post("/v1/auth/otp/send", json={"phone": PHONE})
    assert sent.status_code == 200

    # Typed as a person types it: the endpoint normalises, as send does.
    response = await client.post(LAST_CODE, json={"phone": TYPED})

    assert response.status_code == 200
    assert response.json() == {"code": fake_providers.sms.last_code(PHONE)}
    assert response.json()["code"] is not None


async def test_has_no_code_for_a_number_nothing_was_sent_to(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post(LAST_CODE, json={"phone": TYPED})

    assert response.status_code == 200
    assert response.json() == {"code": None}


async def test_has_no_code_for_a_banned_number_as_its_phone_gets_none(
    db: AsyncSession, client: AsyncClient
) -> None:
    """D-073: a banned number is answered like any other and sent nothing.
    The stored code exists; the outbox, which this reads, has none."""
    db.add(
        BannedIdentity(
            kind=BanKind.PHONE_HASH,
            value=hash_phone(PHONE, make_test_settings()),
            reason="underage",
        )
    )
    await db.flush()

    sent = await client.post("/v1/auth/otp/send", json={"phone": PHONE})
    response = await client.post(LAST_CODE, json={"phone": PHONE})

    assert sent.status_code == 200
    assert response.json() == {"code": None}


async def _app_answer(app: FastAPI) -> int:
    app.dependency_overrides[get_session] = session_for_the_app
    app.state.providers = FakeProviders().as_providers()
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return (await c.post(LAST_CODE, json={"phone": PHONE})).status_code
    finally:
        await close_resources(app)


@pytest.mark.parametrize(
    "update",
    [
        {"ENV": "staging"},
        {"ENV": "production"},
        {"ENV": "preview"},
        # A name nobody has listed anywhere, in any allowlist or test: a
        # blacklist that names today's environments waves it through; the
        # allowlist refuses it (rule 16). The endpoint's code signs anyone in.
        {"ENV": "env-nobody-has-named-2031"},
        {"SMS_PROVIDER": "msg91"},
    ],
    ids=lambda update: ",".join(f"{k}={v}" for k, v in update.items()),
)
async def test_isnt_served_anywhere_else(
    db: AsyncSession, update: dict[str, str]
) -> None:
    """An allowlist both ways (rule 16): local and the fake, nothing else.
    Settings are swapped after validation, which would refuse a fake outside
    local anyway (D-045)."""
    settings = make_test_settings().model_copy(update=update)

    assert await _app_answer(create_app(settings)) == 404


def test_is_never_in_the_schema() -> None:
    """So `make types` is the same everywhere, and the web can't call it."""
    paths = create_app(make_test_settings()).openapi()["paths"]

    assert LAST_CODE not in paths
    assert not [path for path in paths if path.startswith("/v1/test")]


async def test_logs_neither_the_number_nor_the_code(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    await client.post("/v1/auth/otp/send", json={"phone": PHONE})
    response = await client.post(LAST_CODE, json={"phone": TYPED})
    code = response.json()["code"]

    assert code
    for secret in (PHONE, PHONE[3:], TYPED, TYPED.replace(" ", ""), code):
        assert secret not in captured_logs.text
    captured_logs.assert_listening()
