"""`GET /v1/payments/{id}` (T-8.2): what the browser polls after Checkout.
The owner's own payment only, and the same `NOT_FOUND` for anyone else's as
for none; no GST anywhere in it while unregistered (D-482)."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
from app.core.providers import FakeProviders
from tests.conftest import MakeUser
from tests.modules.payments.support import (
    add_payment,
    auth,
    captured,
    deliver,
    order,
)

pytestmark = pytest.mark.usefixtures("test_redis")


def _poll(payment_id: uuid.UUID) -> str:
    return f"/v1/payments/{payment_id}"


async def test_the_owner_sees_the_status_and_the_velas(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    _, token = await make_user()
    payment_id, order_id = await order(client, token, "pack-250")

    created = await client.get(_poll(payment_id), headers=auth(token))
    await deliver(client, fake_providers.payments, captured(order_id, amount=600_000))
    paid = await client.get(_poll(payment_id), headers=auth(token))

    assert created.status_code == 200
    assert created.json() == {"status": "created", "credits": 250, "bonus_credits": 50}
    assert paid.json() == {"status": "paid", "credits": 250, "bonus_credits": 50}


@pytest.mark.parametrize("status", list(PaymentStatus))
async def test_it_says_gst_nowhere_in_any_status(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: PaymentStatus
) -> None:
    """Not a field, not a word, in any case, headers included (D-482)."""
    man, token = await make_user()
    payment = await add_payment(db, man.id, status=status)

    shown = await client.get(_poll(payment.id), headers=auth(token))

    assert shown.status_code == 200
    assert shown.json()["status"] == status.value
    assert "gst" not in shown.text.lower()
    assert "gst" not in json.dumps(dict(shown.headers)).lower()


@pytest.mark.critical
async def test_someone_elses_payment_is_not_found_as_none_is(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    owner, _ = await make_user()
    _, other_token = await make_user()
    payment = await add_payment(db, owner.id, status=PaymentStatus.PAID)

    theirs = await client.get(_poll(payment.id), headers=auth(other_token))
    nobodys = await client.get(_poll(uuid.uuid4()), headers=auth(other_token))

    assert theirs.status_code == nobodys.status_code == 404
    assert theirs.json() == nobodys.json()
    assert theirs.json()["error"]["code"] == "NOT_FOUND"


async def test_signed_out_is_refused(db: AsyncSession, client: AsyncClient) -> None:
    response = await client.get(_poll(uuid.uuid4()))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


async def test_onboarding_unfinished_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(onboarded=False)
    payment = await add_payment(db, man.id, status=PaymentStatus.CREATED)

    response = await client.get(_poll(payment.id), headers=auth(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"
