"""`POST /v1/payments/orders` (T-8.1): priced from the pack's row, never the
browser (rule 6); one order per `Idempotency-Key` (D-481); a woman refused
before any gateway is asked (D-076); and no GST, anywhere she or he is shown
the payment, while Velora is unregistered (D-450, D-482)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
from app.core.providers import FakeProviders
from app.core.providers.payments import PaymentsUnavailable, ProviderOrder
from app.modules.payments import rules
from app.modules.payments.models import CreditPack, Payment
from tests.conftest import MakeUser
from tests.modules.payments.support import add_payment, auth, man_in, new_key

pytestmark = pytest.mark.usefixtures("test_redis")

ORDERS = "/v1/payments/orders"


async def _payments_of(db: AsyncSession, user_id: uuid.UUID) -> list[Payment]:
    return list(
        (await db.scalars(select(Payment).where(Payment.user_id == user_id))).all()
    )


def _error(response: Any) -> str:
    code: str = response.json()["error"]["code"]
    return code


@pytest.mark.parametrize("variant", ["A", "B"])
async def test_a_man_orders_a_pack_at_its_price(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    variant: str,
) -> None:
    man, token = await man_in(make_user, variant)

    response = await client.post(
        ORDERS, json={"pack_id": "pack-100"}, headers=auth(token, new_key())
    )

    assert response.status_code == 200
    body = response.json()
    [payment] = await _payments_of(db, man.id)
    [order] = fake_providers.payments.orders.values()
    assert body == {
        "payment_id": str(payment.id),
        "order_id": order.id,
        "key_id": fake_providers.payments.key_id,
        "amount_paise": 450_000,
    }
    assert (payment.pack_id, payment.amount_paise, payment.credits) == (
        "pack-100",
        450_000,
        100,
    )
    assert payment.bonus_credits == 20  # his first purchase (D-231)
    assert payment.status is PaymentStatus.CREATED
    assert payment.gst_paise == 0
    assert order.amount_paise == 450_000


async def test_the_price_is_the_rows_now(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """A price change is a row update (D-005): the next order copies it."""
    man, token = await make_user()
    await db.execute(
        update(CreditPack).where(CreditPack.id == "pack-30").values(price_paise=149_900)
    )

    response = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
    )

    assert response.json()["amount_paise"] == 149_900
    [payment] = await _payments_of(db, man.id)
    assert payment.amount_paise == 149_900


@pytest.mark.parametrize(
    "extra",
    [{"amount_paise": 100}, {"credits": 450}, {"bonus_credits": 1000}],
    ids=lambda extra: next(iter(extra)),
)
async def test_a_body_naming_a_price_or_velas_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    extra: dict[str, int],
) -> None:
    """Rule 6: the browser names the pack, nothing more."""
    man, token = await make_user()

    response = await client.post(
        ORDERS, json={"pack_id": "pack-30", **extra}, headers=auth(token, new_key())
    )

    assert response.status_code == 400
    assert _error(response) == "VALIDATION_ERROR"
    assert fake_providers.payments.orders == {}
    assert await _payments_of(db, man.id) == []


async def test_a_later_purchase_has_no_bonus(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    await add_payment(db, man.id, status=PaymentStatus.PAID)

    await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
    )

    created = [
        p for p in await _payments_of(db, man.id) if p.status is PaymentStatus.CREATED
    ]
    assert [p.bonus_credits for p in created] == [0]


async def test_a_woman_is_refused_before_any_gateway_is_asked(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """D-076: she could never be credited, so she never pays."""
    woman, token = await make_user("female")

    response = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
    )

    assert response.status_code == 422
    assert _error(response) == "NOT_ALLOWED"
    assert fake_providers.payments.orders == {}
    assert await _payments_of(db, woman.id) == []


@pytest.mark.parametrize("pack_id", ["entry-25", "pack-25", "pack-nope"])
async def test_a_retired_or_unknown_pack_isnt_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    pack_id: str,
) -> None:
    """`entry-25` is variant B's own, retired (D-250): a B man can't order it
    either, since his store is A's (D-480)."""
    _, token = await man_in(make_user, "B")

    response = await client.post(
        ORDERS, json={"pack_id": pack_id}, headers=auth(token, new_key())
    )

    assert response.status_code == 404
    assert _error(response) == "NOT_FOUND"
    assert fake_providers.payments.orders == {}


async def test_a_pack_outside_his_store_isnt_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """An active pack of another variant: not in his store, so not his to buy."""
    _, token = await make_user()
    db.add(CreditPack(id="pack-z", credits=10, price_paise=10_000, variant="Z"))
    await db.flush()

    response = await client.post(
        ORDERS, json={"pack_id": "pack-z"}, headers=auth(token, new_key())
    )

    assert response.status_code == 404


# --- The Idempotency-Key (D-481) ------------------------------------------------


@pytest.mark.parametrize("key", [None, "", "short", "has space in it", "x" * 65])
async def test_a_missing_or_malformed_key_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    key: str | None,
) -> None:
    _, token = await make_user()

    response = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, key)
    )

    assert response.status_code == 400
    assert _error(response) == "VALIDATION_ERROR"
    assert fake_providers.payments.orders == {}


async def test_the_same_key_twice_is_one_order(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, token = await make_user()
    key = new_key()

    first = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, key)
    )
    second = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, key)
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(await _payments_of(db, man.id)) == 1
    assert len(fake_providers.payments.orders) == 1


async def test_the_same_key_with_another_pack_is_already_used(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Returning the first order would hide the client's bug (D-481)."""
    man, token = await make_user()
    man_id = man.id  # the refusal rolls back, which expires `man`
    key = new_key()
    await client.post(ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, key))

    response = await client.post(
        ORDERS, json={"pack_id": "pack-450"}, headers=auth(token, key)
    )

    assert response.status_code == 409
    assert _error(response) == "ALREADY_EXISTS"
    assert [p.pack_id for p in await _payments_of(db, man_id)] == ["pack-30"]


async def test_two_men_may_send_the_same_key(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """A key is the client's, so it is unique per man, never across men."""
    _, one = await make_user()
    _, other = await make_user()
    key = new_key()

    first = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(one, key)
    )
    second = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(other, key)
    )

    assert first.json()["payment_id"] != second.json()["payment_id"]


@pytest.mark.critical  # D-481: a retried click is never a second order
async def test_the_same_key_racing_itself_is_one_order(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The race forced, not hoped for: while the first request waits on the
    gateway, past its look for the key and before its insert, the second runs
    from start to finish with the same key. The first then finds the key taken
    at its insert, and answers with the second's order. Its own gateway order
    is never handed out."""
    man, token = await make_user()
    key = new_key()
    create_order = fake_providers.payments.create_order
    calls = 0
    inner: list[Any] = []

    async def overtaken(*, amount_paise: int, receipt: str) -> ProviderOrder:
        nonlocal calls
        calls += 1
        order = await create_order(amount_paise=amount_paise, receipt=receipt)
        if calls == 1:  # the first request's call: the second overtakes it here
            inner.append(
                await client.post(
                    ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, key)
                )
            )
        return order

    monkeypatch.setattr(fake_providers.payments, "create_order", overtaken)

    outer = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, key)
    )

    assert calls == 2  # both reached the gateway, the second inside the first
    [overtaker] = inner
    assert overtaker.status_code == outer.status_code == 200
    assert outer.json() == overtaker.json()
    assert len(fake_providers.payments.orders) == 2
    [payment] = await _payments_of(db, man.id)
    assert outer.json()["order_id"] == payment.provider_order_id


async def test_the_database_refuses_a_second_order_for_one_key(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The guarantee is Postgres's, whatever the service does (D-481)."""
    man, _ = await make_user()
    first = await add_payment(db, man.id, status=PaymentStatus.CREATED)

    db.add(
        Payment(
            user_id=man.id,
            pack_id="pack-30",
            amount_paise=150_000,
            credits=30,
            idempotency_key=first.idempotency_key,
            provider_order_id="order_test_second",
        )
    )
    with pytest.raises(IntegrityError, match="uq_payments_user_id_idempotency_key"):
        await db.flush()


# --- The gateway -----------------------------------------------------------------


async def test_a_gateway_down_writes_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    man, token = await make_user()

    async def down(*, amount_paise: int, receipt: str) -> ProviderOrder:
        raise PaymentsUnavailable("Razorpay didn't answer: ConnectTimeout")

    monkeypatch.setattr(fake_providers.payments, "create_order", down)

    response = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
    )

    assert response.status_code == 503
    assert _error(response) == "PROVIDER_UNAVAILABLE"
    assert await _payments_of(db, man.id) == []


async def test_the_receipt_is_our_payments_id(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At most 40 ASCII characters and unique, as Razorpay asks: a UUID's 36."""
    _, token = await make_user()
    receipts: list[str] = []
    create_order = fake_providers.payments.create_order

    async def recording(*, amount_paise: int, receipt: str) -> ProviderOrder:
        receipts.append(receipt)
        return await create_order(amount_paise=amount_paise, receipt=receipt)

    monkeypatch.setattr(fake_providers.payments, "create_order", recording)

    response = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
    )

    assert receipts == [response.json()["payment_id"]]
    assert len(receipts[0]) <= 40


async def test_twenty_orders_an_hour(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    answers = [
        (
            await client.post(
                ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
            )
        ).status_code
        for _ in range(21)
    ]

    assert answers == [200] * 20 + [429]


# --- GST (D-450, D-482) -------------------------------------------------------------


@pytest.mark.critical  # D-450: showing GST without a GSTIN is against the law
async def test_an_unregistered_payment_says_gst_nowhere(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Everything a man is shown about a payment, as he receives it: the
    order's response, and the store it was bought from. Not a field, not a
    word, in any case. `GET /payments/{id}` joins with T-8.2."""
    _, token = await make_user()

    store = await client.get("/v1/packs", headers=auth(token))
    order = await client.post(
        ORDERS, json={"pack_id": "pack-30"}, headers=auth(token, new_key())
    )

    assert order.status_code == store.status_code == 200
    for shown in (order, store):
        assert "gst" not in shown.text.lower()
        assert "gst" not in json.dumps(dict(shown.headers)).lower()


async def test_the_database_keeps_gst_inside_the_amount(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Registration splits the inclusive price, never adds to it (D-450)."""
    man, _ = await make_user()
    payment = await add_payment(db, man.id, status=PaymentStatus.CREATED)

    payment.gst_paise = payment.amount_paise
    with pytest.raises(IntegrityError, match="ck_payments_gst_within_amount"):
        await db.flush()


def test_a_registered_split_isnt_built() -> None:
    """The second lock behind Settings' refusal: P-350 builds the split."""
    assert rules.gst_paise(150_000, registered=False) == 0
    with pytest.raises(rules.GstNotBuilt, match="P-350"):
        rules.gst_paise(150_000, registered=True)
