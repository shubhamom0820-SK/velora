"""The fake gateway's webhook simulator (T-8.1): served only where ENV is local
and the payments provider is the fake (rule 16), never in OpenAPI. It delivers
the webhook Razorpay would send for a payment to the API's own webhook route,
signed by the fake, as T-8.2's route will read it."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.providers import FakeProviders
from app.main import close_resources, create_app
from tests.conftest import MakeUser, make_test_settings
from tests.infra import session_for_the_app
from tests.modules.payments.support import auth, new_key

pytestmark = pytest.mark.usefixtures("test_redis")

SIMULATE = "/v1/test/payments/webhook"
WEBHOOK = "/v1/payments/webhook"


async def _order(client: AsyncClient, make_user: MakeUser) -> dict[str, Any]:
    _, token = await make_user()
    response = await client.post(
        "/v1/payments/orders",
        json={"pack_id": "pack-30"},
        headers=auth(token, new_key()),
    )
    assert response.status_code == 200
    order: dict[str, Any] = response.json()
    return order


def _recording(app: FastAPI) -> list[tuple[bytes, str | None]]:
    """A stand-in for T-8.2's webhook route that keeps what arrives."""
    received: list[tuple[bytes, str | None]] = []

    async def webhook(request: Request) -> dict[str, str]:
        received.append(
            (await request.body(), request.headers.get("X-Razorpay-Signature"))
        )
        return {}

    app.add_api_route(WEBHOOK, webhook, methods=["POST"])
    return received


@pytest.mark.parametrize(
    ("outcome", "event", "status"),
    [
        ("captured", "payment.captured", "captured"),
        ("failed", "payment.failed", "failed"),
    ],
)
async def test_it_delivers_the_signed_webhook_razorpay_would_send(
    db: AsyncSession,
    app: FastAPI,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    outcome: str,
    event: str,
    status: str,
) -> None:
    order = await _order(client, make_user)
    received = _recording(app)

    response = await client.post(
        SIMULATE, json={"payment_id": order["payment_id"], "outcome": outcome}
    )

    assert response.json() == {"delivered_status": 200}
    [(body, signature)] = received
    assert signature is not None
    assert fake_providers.payments.verify_webhook(body, signature) is True
    sent = json.loads(body)
    assert sent["event"] == event
    entity = sent["payload"]["payment"]["entity"]
    assert (entity["order_id"], entity["amount"], entity["status"]) == (
        order["order_id"],
        order["amount_paise"],
        status,
    )


async def test_it_can_fake_an_amount_mismatch(
    db: AsyncSession,
    app: FastAPI,
    client: AsyncClient,
    make_user: MakeUser,
) -> None:
    """For T-8.2's "amount mismatch → no credit"."""
    order = await _order(client, make_user)
    received = _recording(app)

    await client.post(
        SIMULATE,
        json={
            "payment_id": order["payment_id"],
            "outcome": "captured",
            "amount_paise": 100,
        },
    )

    [(body, _)] = received
    assert json.loads(body)["payload"]["payment"]["entity"]["amount"] == 100


async def test_it_works_after_the_api_restarts(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    app: FastAPI,
) -> None:
    """The fake's orders are in memory and gone with a restart; the webhook is
    built from the `payments` row, which isn't."""
    order = await _order(client, make_user)
    fake_providers.payments.orders.clear()
    received = _recording(app)

    response = await client.post(
        SIMULATE, json={"payment_id": order["payment_id"], "outcome": "captured"}
    )

    assert response.json() == {"delivered_status": 200}
    assert len(received) == 1


async def test_until_t82_builds_the_webhook_route_the_delivery_finds_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    order = await _order(client, make_user)

    response = await client.post(
        SIMULATE, json={"payment_id": order["payment_id"], "outcome": "captured"}
    )

    assert response.json() == {"delivered_status": 404}


async def test_an_unknown_payment_isnt_found(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post(
        SIMULATE,
        json={
            "payment_id": "00000000-0000-4000-8000-000000000000",
            "outcome": "captured",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


UNKNOWN = {"payment_id": "00000000-0000-4000-8000-000000000000", "outcome": "captured"}


async def _answers(app: FastAPI) -> tuple[tuple[int, Any], tuple[int, Any]]:
    """The simulator's answer, and the same app's answer at a path nothing
    serves: equal only when the simulator isn't mounted."""
    app.dependency_overrides[get_session] = session_for_the_app
    app.state.providers = FakeProviders().as_providers()
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            simulator = await c.post(SIMULATE, json=UNKNOWN)
            nothing = await c.post("/v1/test/payments/nothing-here", json=UNKNOWN)
    finally:
        await close_resources(app)
    return (
        (simulator.status_code, simulator.json()),
        (nothing.status_code, nothing.json()),
    )


async def test_it_is_served_locally_beside_the_fake(db: AsyncSession) -> None:
    """The control for the refusals below: here the route exists, and answers
    an unknown payment with its own 404, not the router's."""
    simulator, nothing = await _answers(create_app(make_test_settings()))

    assert simulator[0] == 404
    assert simulator[1]["error"]["message"] == "No such payment."
    assert simulator != nothing


@pytest.mark.parametrize(
    "update",
    [
        {"ENV": "staging"},
        {"ENV": "production"},
        {"ENV": "preview"},
        # A name nobody has listed anywhere: a blacklist of today's names
        # would serve it; the allowlist refuses it (rule 16). This route pays
        # for Velas with nothing.
        {"ENV": "env-nobody-has-named-2031"},
        {"PAYMENTS_PROVIDER": "razorpay"},
    ],
    ids=lambda update: ",".join(f"{k}={v}" for k, v in update.items()),
)
async def test_isnt_served_anywhere_else(
    db: AsyncSession, update: dict[str, str]
) -> None:
    """Settings swapped after validation, which would refuse a fake outside
    local anyway (D-045)."""
    settings = make_test_settings().model_copy(update=update)

    simulator, nothing = await _answers(create_app(settings))

    assert simulator[0] == 404
    assert simulator == nothing


def test_is_never_in_the_schema() -> None:
    paths = create_app(make_test_settings()).openapi()["paths"]

    assert SIMULATE not in paths
    assert not [path for path in paths if path.startswith("/v1/test")]
