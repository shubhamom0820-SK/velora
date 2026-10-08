"""SQL for packs and payments. No rules here: the service decides."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, PaymentStatus
from app.modules.payments.models import CreditPack, Payment
from app.modules.users.models import User


async def active_packs(session: AsyncSession, variant: str) -> Sequence[CreditPack]:
    """The variant's active packs, in the store's order."""
    rows = await session.scalars(
        select(CreditPack)
        .where(CreditPack.variant == variant, CreditPack.active.is_(True))
        .order_by(CreditPack.sort, CreditPack.id)
    )
    return rows.all()


async def active_pack(
    session: AsyncSession, pack_id: str, variant: str
) -> CreditPack | None:
    """The pack, if it is active and in the variant's store; None otherwise."""
    pack: CreditPack | None = await session.scalar(
        select(CreditPack).where(
            CreditPack.id == pack_id,
            CreditPack.variant == variant,
            CreditPack.active.is_(True),
        )
    )
    return pack


async def has_bought(session: AsyncSession, user_id: UUID) -> bool:
    """Whether money has ever moved for this user: a payment paid, or paid and
    later refunded."""
    found = await session.scalar(
        select(Payment.id)
        .where(
            Payment.user_id == user_id,
            Payment.status.in_((PaymentStatus.PAID, PaymentStatus.REFUNDED)),
        )
        .limit(1)
    )
    return found is not None


async def payment_by_key(
    session: AsyncSession, user_id: UUID, key: str
) -> Payment | None:
    payment: Payment | None = await session.scalar(
        select(Payment).where(
            Payment.user_id == user_id, Payment.idempotency_key == key
        )
    )
    return payment


async def payment_by_id(session: AsyncSession, payment_id: UUID) -> Payment | None:
    return await session.get(Payment, payment_id)


MONEY_MOVED = (PaymentStatus.PAID, PaymentStatus.REFUNDED)


async def lock_payment(
    session: AsyncSession,
    *,
    order_id: str | None = None,
    provider_payment_id: str | None = None,
) -> Payment | None:
    """The payment with this gateway order, or this gateway payment, its row
    locked until the transaction ends; None if there is none. Read afresh, so
    a copy already in the session never stands in for the locked row."""
    query = select(Payment).with_for_update().execution_options(populate_existing=True)
    if order_id is not None:
        query = query.where(Payment.provider_order_id == order_id)
    elif provider_payment_id is not None:
        query = query.where(Payment.provider_payment_id == provider_payment_id)
    else:
        raise ValueError("lock_payment needs an order id or a payment id")
    payment: Payment | None = await session.scalar(query)
    return payment


async def owner_gender(session: AsyncSession, user_id: UUID) -> Gender | None:
    gender: Gender | None = await session.scalar(
        select(User.gender).where(User.id == user_id)
    )
    return gender


async def bought_other_than(
    session: AsyncSession, user_id: UUID, payment_id: UUID
) -> bool:
    """Whether money has moved for this user on any payment but this one: paid,
    or paid and later refunded."""
    found = await session.scalar(
        select(Payment.id)
        .where(
            Payment.user_id == user_id,
            Payment.id != payment_id,
            Payment.status.in_(MONEY_MOVED),
        )
        .limit(1)
    )
    return found is not None


async def add_payment(
    session: AsyncSession,
    *,
    payment_id: UUID,
    user_id: UUID,
    key: str,
    pack_id: str,
    amount_paise: int,
    credits: int,
    bonus_credits: int,
    gst_paise: int,
    provider_order_id: str,
) -> Payment | None:
    """The new `created` payment, or None if this user's key is taken already:
    the unique key is the arbiter, so a request that lost a race writes nothing.
    Any other conflict, a reused order id, raises."""
    payment: Payment | None = await session.scalar(
        insert(Payment)
        .values(
            id=payment_id,
            user_id=user_id,
            idempotency_key=key,
            pack_id=pack_id,
            amount_paise=amount_paise,
            credits=credits,
            bonus_credits=bonus_credits,
            gst_paise=gst_paise,
            provider_order_id=provider_order_id,
        )
        .on_conflict_do_nothing(constraint="uq_payments_user_id_idempotency_key")
        .returning(Payment)
    )
    return payment


async def turnover(
    session: AsyncSession, starts_at: datetime, ends_at: datetime
) -> tuple[int, int]:
    """`(sum of amount_paise, count)` of the payments paid in `[starts_at,
    ends_at)`. From `payments` alone, never the ledger: turnover is money in,
    and bonus Velas aren't money (D-483)."""
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(Payment.amount_paise), 0), func.count()
            ).where(
                Payment.status == PaymentStatus.PAID,
                Payment.paid_at >= starts_at,
                Payment.paid_at < ends_at,
            )
        )
    ).one()
    return int(row[0]), int(row[1])
