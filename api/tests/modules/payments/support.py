"""What the payments tests share: men in a chosen variant, payments written
straight to the table as the webhook leaves them, and Razorpay's events,
signed by the fake and delivered to the webhook (T-8.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
from app.core.providers.payments import FakePayments
from app.modules.payments import rules
from app.modules.payments.models import Payment
from app.modules.users.models import User
from tests.conftest import MakeUser

# D-099's packs, in the store's order: id, Velas, price in paise, bonus (D-231).
LADDER = [
    ("pack-30", 30, 150_000, 6),
    ("pack-100", 100, 450_000, 20),
    ("pack-250", 250, 600_000, 50),
    ("pack-450", 450, 1_000_000, 90),
]


# When a paid payment was paid, unless a test says.
PAID_AT = datetime(2026, 10, 8, 6, 0, tzinfo=UTC)


def auth(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def new_key() -> str:
    return str(uuid.uuid4())


async def man_in(make_user: MakeUser, variant: str) -> tuple[User, str]:
    """A man whose id hashes into `variant`: about two tries each."""
    for _ in range(64):
        user, token = await make_user()
        if rules.variant_of(user.id) == variant:
            return user, token
    raise AssertionError(f"64 men and none in variant {variant}: is the hash broken?")


async def add_payment(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: PaymentStatus,
    amount_paise: int = 150_000,
    paid_at: datetime | None = None,
    pack_id: str = "pack-30",
) -> Payment:
    """A payment as the webhook will leave it: paid ones carry their anchor."""
    moved = status in (PaymentStatus.PAID, PaymentStatus.REFUNDED)
    payment = Payment(
        user_id=user_id,
        pack_id=pack_id,
        amount_paise=amount_paise,
        credits=30,
        idempotency_key=new_key(),
        provider_order_id=f"order_test_{uuid.uuid4().hex}",
        provider_payment_id=f"pay_test_{uuid.uuid4().hex}" if moved else None,
        status=status,
        paid_at=(paid_at or PAID_AT) if moved else None,
    )
    db.add(payment)
    await db.flush()
    return payment


# --- Razorpay's events, as its docs show them (T-8.2) -----------------------------

WEBHOOK = "/v1/payments/webhook"
SIGNATURE = "X-Razorpay-Signature"


def payment_entity(
    order_id: str,
    *,
    payment_id: str | None = None,
    amount: int = 150_000,
    currency: str = "INR",
    status: str = "captured",
    **extra: Any,
) -> dict[str, Any]:
    """The order's payment: its id is `pay_for_<order>` unless named, so two
    orders' payments never share the anchor."""
    return {
        "id": payment_id or f"pay_for_{order_id}",
        "entity": "payment",
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "status": status,
        "method": "upi",
        "error_code": None,
        "created_at": 1_759_900_000,
        **extra,
    }


def event(name: str, **entities: dict[str, Any]) -> dict[str, Any]:
    """A webhook body: `event(name, payment=..., refund=...)`."""
    return {
        "entity": "event",
        "account_id": "acc_test",
        "event": name,
        "contains": list(entities),
        "payload": {key: {"entity": value} for key, value in entities.items()},
        "created_at": 1_759_900_100,
    }


def captured(order_id: str, **payment: Any) -> dict[str, Any]:
    return event("payment.captured", payment=payment_entity(order_id, **payment))


def failed(order_id: str, **payment: Any) -> dict[str, Any]:
    return event(
        "payment.failed",
        payment=payment_entity(
            order_id,
            **{"status": "failed", "error_code": "BAD_REQUEST_ERROR", **payment},
        ),
    )


def refund(
    name: str, order_id: str, *, refund_id: str = "rfnd_test_1", **payment: Any
) -> dict[str, Any]:
    """`refund.created`, `.processed` or `.failed`, carrying its payment."""
    entity = payment_entity(order_id, **payment)
    return event(
        name,
        refund={
            "id": refund_id,
            "entity": "refund",
            "payment_id": entity["id"],
            "amount": entity["amount"],
            "currency": "INR",
            "status": name.removeprefix("refund."),
            "created_at": 1_759_900_200,
        },
        payment=entity,
    )


def dispute(
    name: str, order_id: str, *, dispute_id: str = "disp_test_1", **payment: Any
) -> dict[str, Any]:
    """`payment.dispute.created`, `.won` or `.lost`, carrying its payment."""
    entity = payment_entity(order_id, **payment)
    return event(
        name,
        payment=entity,
        dispute={
            "id": dispute_id,
            "entity": "dispute",
            "payment_id": entity["id"],
            "amount": entity["amount"],
            "currency": "INR",
            "amount_deducted": 0,
            "reason_code": "chargeback",
            "status": name.removeprefix("payment.dispute."),
            "phase": "chargeback",
            "created_at": 1_759_900_300,
        },
    )


async def deliver(
    client: AsyncClient, payments: FakePayments, body: dict[str, Any]
) -> Response:
    """The event, signed by the fake as Razorpay would sign it, to the route."""
    signed = payments.sign(body)
    return await client.post(
        WEBHOOK,
        content=signed.body,
        headers={"Content-Type": "application/json", SIGNATURE: signed.signature},
    )


async def order(
    client: AsyncClient, token: str, pack_id: str = "pack-30"
) -> tuple[uuid.UUID, str]:
    """A real order, through the route: our payment's id and the gateway's."""
    response = await client.post(
        "/v1/payments/orders", json={"pack_id": pack_id}, headers=auth(token, new_key())
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return uuid.UUID(body["payment_id"]), body["order_id"]
