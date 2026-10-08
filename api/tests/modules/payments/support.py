"""What the payments tests share: men in a chosen variant, and payments
written straight to the table, as T-8.2's webhook will leave them."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
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
