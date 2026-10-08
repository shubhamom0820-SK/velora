"""Packs, orders and turnover (T-8.1). Velas are credited only by the verified
webhook (T-8.2): nothing here touches the wallet.

**Only a man is sold anything** (D-076). A woman can never hold a Vela, so she
is refused the store and the order, `NOT_ALLOWED`, before any gateway is asked:
she never pays for something she could never use, and a web bug that opens a
store for her fails loudly. An allowlist: anyone not a man is refused.

**An order, in this order:**

1. Refuse anyone but a man.
2. If this man's `Idempotency-Key` has an order already, return it: the same
   pack's, as it was made; another pack's is `ALREADY_EXISTS`, since returning
   it would hide the client's bug (D-481).
3. The pack must be active and in his store, or `NOT_FOUND`. Its row prices the
   order: amount and Velas copied from it, never from the browser (rule 6).
4. The first-purchase bonus, if money has never moved for him (D-231).
5. The gateway's order, outside any transaction, with our payment's id as its
   receipt. Down or refusing, `PROVIDER_UNAVAILABLE`, and nothing is written.
6. The `created` row, `gst_paise` 0 (D-450). If the same key won a race since
   step 2, the row isn't written and the winner's order is returned: the
   gateway order made here is never handed out, so it can't be paid.

**Turnover** (D-483) is the financial year's paid payments, summed from
`payments`, never the ledger: money in, not Velas, so bonuses never count.
"""

from __future__ import annotations

from datetime import UTC
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender
from app.core.errors import AppError
from app.core.providers.payments import PaymentsProvider, PaymentsUnavailable
from app.modules.admin import service as admin_service
from app.modules.payments import repository, rules
from app.modules.payments.models import Payment
from app.modules.payments.rules import FinancialYear, TurnoverLevel
from app.modules.payments.schemas import Order, Pack, PaymentStatusView, Turnover
from app.modules.users.models import User

log = structlog.get_logger(__name__)


class StoreEmpty(Exception):
    """A man's store has no active pack: a catalogue fault, never shown to him
    as an empty list (D-480), so it reaches him as a 500, and is logged."""


def _refuse_unless_man(user: User) -> None:
    if user.gender is not Gender.MALE:
        raise AppError(
            "NOT_ALLOWED",
            "There's nothing to buy here: it's all free for you.",
            status=422,
        )


async def packs_for(session: AsyncSession, user: User) -> list[Pack]:
    """The packs in this man's store, in order, each with the bonus he would
    get buying it now. Never empty."""
    _refuse_unless_man(user)
    variant = rules.store_variant(user.id)
    async with session.begin():
        packs = await repository.active_packs(session, variant)
        first = not await repository.has_bought(session, user.id)
    if not packs:
        log.error("payments.store_empty", variant=variant)
        raise StoreEmpty(f"variant {variant} has no active pack (D-480)")
    return [
        Pack(
            id=pack.id,
            credits=pack.credits,
            price_paise=pack.price_paise,
            bonus_credits=rules.first_purchase_bonus(
                pack.credits, pack.bonus_first_pct, first=first
            ),
        )
        for pack in packs
    ]


async def create_order(
    session: AsyncSession,
    user: User,
    payments: PaymentsProvider,
    *,
    pack_id: str,
    key: str,
    gst_registered: bool,
) -> Order:
    """The order for `pack_id` under this man's `key`: made now, or the one the
    key already has."""
    _refuse_unless_man(user)
    async with session.begin():
        existing = await repository.payment_by_key(session, user.id, key)
        if existing is not None:
            return _replayed(existing, pack_id, payments.key_id)
        pack = await repository.active_pack(
            session, pack_id, rules.store_variant(user.id)
        )
        first = not await repository.has_bought(session, user.id)
    if pack is None:
        raise AppError("NOT_FOUND", "That pack isn't available.", status=404)

    payment_id = uuid4()
    try:
        order = await payments.create_order(
            amount_paise=pack.price_paise, receipt=str(payment_id)
        )
    except PaymentsUnavailable as refusal:
        log.warning("payments.order_unavailable", reason=str(refusal))
        raise AppError(
            "PROVIDER_UNAVAILABLE",
            "Payments aren't working right now. Try again in a few minutes.",
            status=503,
        ) from None

    async with session.begin():
        payment = await repository.add_payment(
            session,
            payment_id=payment_id,
            user_id=user.id,
            key=key,
            pack_id=pack.id,
            amount_paise=pack.price_paise,
            credits=pack.credits,
            bonus_credits=rules.first_purchase_bonus(
                pack.credits, pack.bonus_first_pct, first=first
            ),
            gst_paise=rules.gst_paise(pack.price_paise, registered=gst_registered),
            provider_order_id=order.id,
        )
        if payment is None:
            winner = await repository.payment_by_key(session, user.id, key)
            assert winner is not None  # the key's conflict was this row
            log.info("payments.order_raced", payment_id=str(winner.id))
            return _replayed(winner, pack_id, payments.key_id)
    log.info(
        "payments.order_created",
        user_id=str(user.id),
        payment_id=str(payment.id),
        pack_id=payment.pack_id,
    )
    return _order(payment, payments.key_id)


def _replayed(payment: Payment, pack_id: str, key_id: str) -> Order:
    if payment.pack_id != pack_id:
        raise AppError(
            "ALREADY_EXISTS",
            "This request was already used for another pack.",
            status=409,
        )
    return _order(payment, key_id)


def _order(payment: Payment, key_id: str) -> Order:
    return Order(
        payment_id=payment.id,
        order_id=payment.provider_order_id,
        key_id=key_id,
        amount_paise=payment.amount_paise,
    )


async def status_of(
    session: AsyncSession, user: User, payment_id: UUID
) -> PaymentStatusView:
    """`GET /payments/{id}`: the owner's own payment, or `NOT_FOUND`, the same
    for someone else's as for none, so an id says nothing about another man."""
    async with session.begin():
        payment = await repository.payment_by_id(session, payment_id)
        if payment is None or payment.user_id != user.id:
            raise AppError("NOT_FOUND", "No such payment.", status=404)
        return PaymentStatusView(
            status=payment.status,
            credits=payment.credits,
            bonus_credits=payment.bonus_credits,
        )


async def order_of(session: AsyncSession, payment_id: UUID) -> tuple[str, int] | None:
    """A payment's gateway order and amount, for the local-only simulator."""
    async with session.begin():
        payment = await repository.payment_by_id(session, payment_id)
        return (
            None
            if payment is None
            else (payment.provider_order_id, payment.amount_paise)
        )


# --- Turnover (D-483) --------------------------------------------------------------


async def turnover(session: AsyncSession, year: FinancialYear) -> Turnover:
    """The year's paid payments, summed. Runs inside the caller's transaction."""
    paise, count = await repository.turnover(session, year.starts_at, year.ends_at)
    return Turnover(
        financial_year=year.label,
        # In UTC, as every time the API sends (02-ARCHITECTURE §3).
        starts_at=year.starts_at.astimezone(UTC),
        ends_at=year.ends_at.astimezone(UTC),
        turnover_paise=paise,
        paid_payments=count,
        alert_at_paise=rules.TURNOVER_ALERT_PAISE,
        threshold_paise=rules.GST_THRESHOLD_PAISE,
    )


async def turnover_for_admin(
    session: AsyncSession, admin_id: UUID, first_year: int | None
) -> Turnover:
    """`GET /admin/turnover`: the year asked for, or this one, audited."""
    year = (
        FinancialYear(first_year)
        if first_year is not None
        else rules.financial_year_of(clock.now())
    )
    async with session.begin():
        figure = await turnover(session, year)
        await admin_service.audit(
            session, admin_id, "turnover.read", {"financial_year": year.label}
        )
    return figure


async def log_turnover(session: AsyncSession) -> TurnoverLevel:
    """The worker's daily line (D-483): this year's figure, at warning from ₹15
    lakh and error from ₹20 lakh, where the founder has 30 days to register
    (P-350). Until T-9.12 routes it, the line reaches Fly's logs only (P-381)."""
    year = rules.financial_year_of(clock.now())
    async with session.begin():
        figure = await turnover(session, year)
    level = rules.turnover_level(figure.turnover_paise)
    fields = {
        "financial_year": figure.financial_year,
        "turnover_paise": figure.turnover_paise,
        "paid_payments": figure.paid_payments,
        "alert_at_paise": figure.alert_at_paise,
        "threshold_paise": figure.threshold_paise,
    }
    if level is TurnoverLevel.ERROR:
        log.error(
            "payments.turnover",
            note="Past ₹20 lakh this financial year: register within 30 days (P-350).",
            **fields,
        )
    elif level is TurnoverLevel.WARNING:
        log.warning(
            "payments.turnover",
            note="Past ₹15 lakh this financial year: ₹20 lakh needs registering (P-350).",
            **fields,
        )
    else:
        log.info("payments.turnover", **fields)
    return level
