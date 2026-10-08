"""`POST /v1/refund-requests` (T-8.3, D-580): a broken payment's claim, on the
caller's own payment, one open at a time, never a change of mind."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
from app.core.providers import FakeProviders
from app.modules.payments.models import RefundRequest
from app.modules.payments.router import CLAIMS_PER_DAY
from tests.conftest import MakeUser
from tests.modules.payments.support import add_payment, auth, captured, deliver, order

pytestmark = pytest.mark.usefixtures("test_redis")

PATH = "/v1/refund-requests"


async def _claims(db: AsyncSession, payment_id: uuid.UUID) -> list[RefundRequest]:
    return list(
        (
            await db.scalars(
                select(RefundRequest).where(RefundRequest.payment_id == payment_id)
            )
        ).all()
    )


@pytest.mark.critical
@pytest.mark.parametrize("reason", ["missing_velas", "duplicate_charge"])
async def test_a_man_files_a_claim_on_his_own_payment(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    reason: str,
) -> None:
    """A `created` row: the money may have gone through with no webhook."""
    man, token = await make_user()
    payment_id, _ = await order(client, token)

    response = await client.post(
        PATH,
        json={"payment_id": str(payment_id), "reason": reason},
        headers=auth(token),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"id", "payment_id", "reason", "status", "created_at"}
    assert (body["payment_id"], body["reason"], body["status"]) == (
        str(payment_id),
        reason,
        "open",
    )
    [claim] = await _claims(db, payment_id)
    assert (claim.user_id, str(claim.id)) == (man.id, body["id"])


async def test_another_mans_payment_and_none_are_the_same_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    owner, _ = await make_user()
    _, token = await make_user()
    theirs = (await add_payment(db, owner.id, status=PaymentStatus.CREATED)).id

    answers = [
        await client.post(
            PATH,
            json={"payment_id": str(payment_id), "reason": "duplicate_charge"},
            headers=auth(token),
        )
        for payment_id in (theirs, uuid.uuid4())
    ]

    assert [a.status_code for a in answers] == [404, 404]
    assert answers[0].json() == answers[1].json()
    assert answers[0].json()["error"]["code"] == "NOT_FOUND"
    assert await _claims(db, theirs) == []


@pytest.mark.parametrize("status", [PaymentStatus.PAID, PaymentStatus.REFUNDED])
async def test_missing_velas_on_a_payment_that_granted_them_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: PaymentStatus
) -> None:
    """A duplicate charge on it is still a claim: the second payment on the
    order has no Velas."""
    man, token = await make_user()
    payment_id = (await add_payment(db, man.id, status=status)).id

    missing = await client.post(
        PATH,
        json={"payment_id": str(payment_id), "reason": "missing_velas"},
        headers=auth(token),
    )
    duplicate = await client.post(
        PATH,
        json={"payment_id": str(payment_id), "reason": "duplicate_charge"},
        headers=auth(token),
    )

    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "NOT_ALLOWED"
    assert missing.json()["error"]["details"] == {"why": "velas_granted"}
    assert duplicate.status_code == 201


async def test_missing_velas_after_a_real_capture_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    _, token = await make_user()
    payment_id, order_id = await order(client, token)
    await deliver(client, fake_providers.payments, captured(order_id))

    response = await client.post(
        PATH,
        json={"payment_id": str(payment_id), "reason": "missing_velas"},
        headers=auth(token),
    )

    assert response.json()["error"]["code"] == "NOT_ALLOWED"


@pytest.mark.critical
async def test_a_second_open_claim_on_one_payment_already_exists(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    payment_id, _ = await order(client, token)
    first = await client.post(
        PATH,
        json={"payment_id": str(payment_id), "reason": "missing_velas"},
        headers=auth(token),
    )

    second = await client.post(
        PATH,
        json={"payment_id": str(payment_id), "reason": "duplicate_charge"},
        headers=auth(token),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_EXISTS"
    assert len(await _claims(db, payment_id)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"payment_id": "PAYMENT", "reason": "changed_my_mind"},
        {"payment_id": "PAYMENT"},
        {"payment_id": "not-a-uuid", "reason": "missing_velas"},
        {"payment_id": "PAYMENT", "reason": "missing_velas", "details": "I want"},
    ],
    ids=["a change of mind", "no reason", "not an id", "words of his own"],
)
async def test_anything_but_a_payment_and_a_kind_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: dict[str, str]
) -> None:
    _, token = await make_user()
    payment_id, _ = await order(client, token)
    sent = {
        key: str(payment_id) if value == "PAYMENT" else value
        for key, value in body.items()
    }

    response = await client.post(PATH, json=sent, headers=auth(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert await _claims(db, payment_id) == []


async def test_without_a_token_it_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post(
        PATH, json={"payment_id": str(uuid.uuid4()), "reason": "missing_velas"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


async def test_past_ten_a_day_it_is_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Refused claims count too: the limit is on asking."""
    assert CLAIMS_PER_DAY == 10
    _, token = await make_user()
    body = {"payment_id": str(uuid.uuid4()), "reason": "missing_velas"}
    for _ in range(CLAIMS_PER_DAY):
        assert (
            await client.post(PATH, json=body, headers=auth(token))
        ).status_code == 404

    limited = await client.post(PATH, json=body, headers=auth(token))

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
