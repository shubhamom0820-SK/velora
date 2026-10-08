"""Razorpay's webhook (T-8.2): what each verified event does to a payment and
its Velas, one transaction per event (D-520 to D-524).

**Velas come from the `payments` row, never the webhook** (rule 6): the
webhook says which payment and that it was captured; the row says what it was
worth. An amount or currency the row doesn't hold marks it `failed` and credits
nothing.

**Every event may arrive twice, late, or out of order** (Razorpay's docs). So:

- The row is locked (`SELECT ... FOR UPDATE`) for the event's whole
  transaction, and the wallet's own key (`purchase` + our payment's id, D-077)
  catches anything past it.
- `provider_payment_id` is the idempotency anchor, set only by a capture. A
  failed attempt never sets it: one order can fail and then be captured (a UPI
  retry), and that capture must still credit (D-523).
- A refund or dispute that reaches an order not yet captured applies the
  capture first, from the signed payment inside that same event, then reverses
  it: money never goes back while its Velas stand (D-076 rule 3).

**A capture, in this order:** the row by its order; a repeat or a second
payment on one order credits nothing; the amount and currency; the owner must be
a man (D-076); then `paid`, the anchor, `paid_at` by our clock (D-523), and
`purchase`, which locks the wallet. Only then is the bonus decided: none if any
other payment of his has moved money, read under the wallet's lock, so two
captures at once grant it once (D-522, P-380).

**Reversals** (D-520): on `refund.created` and `payment.dispute.created`, the
Velas the payment granted are taken back, what the balance holds, down to 0
(`wallet.reverse()`); the rest is a shortfall, logged, and on a dispute a
`chargeback_shortfall` signal. A failed refund or a dispute won gives back
exactly what its reversal took. The status follows the money: `refunded` on
`refund.processed` and `payment.dispute.lost` only. **Each refund or dispute
is handled once, by its own id** (`payment_reversals`, P-420, D-581), whatever
it took: one that found nothing to take, redelivered after he has bought Velas
again, takes none of them.

**`raw_webhook` keeps an allowlist** of the event's fields (D-524), never the
payer's details, and never a field Razorpay adds later. Logs name the event,
our payment and its order: never payer data, never the body (rule 15).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

import structlog
from pydantic import BaseModel, StrictInt, StrictStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, LedgerReason, PaymentStatus
from app.core.errors import AppError
from app.core.providers.payments import PaymentsProvider, ProviderPayment
from app.modules.payments import repository
from app.modules.payments.models import Payment
from app.modules.safety import service as safety_service
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType

log = structlog.get_logger(__name__)

CURRENCY: Final = "INR"


class WebhookUnreadable(Exception):
    """Signed, so Razorpay's, but not an event we can read: a 500, so Razorpay
    retries it while we fix the reader. The message never carries the body."""


class Outcome(StrEnum):
    """What one event did. The route answers 200 whatever it is."""

    CAPTURED = "captured"
    REPEAT = "repeat"
    SECOND_CAPTURE = "second_capture"
    MISMATCH = "mismatch"
    NOT_A_MAN = "not_a_man"
    FAILED = "failed"
    UNCHANGED = "unchanged"
    REVERSED = "reversed"
    RESTORED = "restored"
    REFUNDED = "refunded"
    NOTHING_TO_DO = "nothing_to_do"
    UNKNOWN_ORDER = "unknown_order"
    IGNORED = "ignored"


# --- The events --------------------------------------------------------------


class PaymentEntity(BaseModel):
    """The fields of Razorpay's payment entity we read. Anything else in it is
    ignored here and never stored."""

    id: StrictStr
    order_id: StrictStr
    amount: StrictInt
    currency: StrictStr


class RefundEntity(BaseModel):
    """A refund's or a dispute's entity: its own id and the payment it is of."""

    id: StrictStr
    payment_id: StrictStr


CAPTURED: Final = "payment.captured"
FAILED: Final = "payment.failed"
REVERSE: Final = {"refund.created": "refund", "payment.dispute.created": "dispute"}
RESTORE: Final = {"refund.failed": "refund", "payment.dispute.won": "dispute"}
SETTLE: Final = {"refund.processed": "refund", "payment.dispute.lost": "dispute"}


@dataclass(frozen=True)
class Event:
    """A verified event, read. `payment` is None for an event we don't handle."""

    name: str
    payment: PaymentEntity | None = None
    # The refund or the dispute, for the events that carry one.
    other: RefundEntity | None = None
    kind: str | None = None  # "refund" or "dispute"
    raw: dict[str, Any] = field(default_factory=dict)


def read(body: bytes) -> Event:
    """The event in a verified body. An event we don't handle is read only for
    its name; one we do must carry what it needs, or it is unreadable."""
    try:
        parsed = json.loads(body)
    except ValueError:
        raise WebhookUnreadable("the body isn't JSON") from None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("event"), str):
        raise WebhookUnreadable("the body has no event name")
    name: str = parsed["event"]
    kind = REVERSE.get(name) or RESTORE.get(name) or SETTLE.get(name)
    if name not in (CAPTURED, FAILED) and kind is None:
        return Event(name=name)
    try:
        payment = PaymentEntity.model_validate(_entity(parsed, "payment"))
        other = (
            None if kind is None else RefundEntity.model_validate(_entity(parsed, kind))
        )
    except (ValidationError, WebhookUnreadable):
        raise WebhookUnreadable(f"{name} lacks the fields it needs") from None
    if other is not None and other.payment_id != payment.id:
        raise WebhookUnreadable(f"{name}'s {kind} names another payment")
    return Event(
        name=name, payment=payment, other=other, kind=kind, raw=raw_webhook(parsed)
    )


def _entity(parsed: Mapping[str, Any], name: str) -> Any:
    payload = parsed.get("payload")
    holder = payload.get(name) if isinstance(payload, dict) else None
    if not isinstance(holder, dict) or "entity" not in holder:
        raise WebhookUnreadable(f"no {name} entity")
    return holder["entity"]


# --- `raw_webhook`: an allowlist (D-524) -----------------------------------------

# Exactly these, and nothing else: never the payer's email, phone (`contact`),
# UPI ID (`vpa`), card, bank, wallet, `acquirer_data`, `notes` or
# `description`, nor any field Razorpay adds later.
RAW_TOP: Final = ("event", "created_at")
RAW_ENTITIES: Final = {
    "payment": (
        "id",
        "order_id",
        "amount",
        "currency",
        "status",
        "method",
        "error_code",
        "created_at",
    ),
    "refund": ("id", "payment_id", "amount", "currency", "status", "created_at"),
    "dispute": ("id", "payment_id", "amount", "currency", "status", "created_at"),
}


def raw_webhook(parsed: Mapping[str, Any]) -> dict[str, Any]:
    """What `payments.raw_webhook` keeps of a verified event: the allowlisted
    fields, flattened, `{event, created_at, payment: {...}, refund: {...}}`."""
    kept: dict[str, Any] = {key: parsed[key] for key in RAW_TOP if key in parsed}
    payload = parsed.get("payload")
    for name, keys in RAW_ENTITIES.items():
        holder = payload.get(name) if isinstance(payload, dict) else None
        entity = holder.get("entity") if isinstance(holder, dict) else None
        if isinstance(entity, dict):
            kept[name] = {key: entity[key] for key in keys if key in entity}
    return kept


# --- The route's work ----------------------------------------------------------------


async def receive(
    session: AsyncSession,
    payments: PaymentsProvider,
    body: bytes,
    signature: str | None,
) -> Outcome:
    """Verify, read and apply one delivery. A bad or missing signature is
    `400 VALIDATION_ERROR`, having read nothing."""
    if signature is None or not payments.verify_webhook(body, signature):
        log.warning(
            "payments.webhook_refused",
            reason="no signature" if signature is None else "bad signature",
        )
        raise AppError(
            "VALIDATION_ERROR", "The webhook's signature doesn't match.", status=400
        )
    try:
        event = read(body)
    except WebhookUnreadable as unreadable:
        log.error("payments.webhook_unreadable", reason=str(unreadable))
        raise
    async with session.begin():
        return await apply(session, event)


async def apply(session: AsyncSession, event: Event) -> Outcome:
    """One verified event, in the caller's transaction."""
    if event.payment is None:
        log.info("payments.webhook_ignored", webhook_event=event.name)
        return Outcome.IGNORED
    if event.name in (CAPTURED, FAILED):
        row = await repository.lock_payment(session, order_id=event.payment.order_id)
    else:
        assert event.other is not None
        row = await repository.lock_payment(
            session, provider_payment_id=event.other.payment_id
        ) or await repository.lock_payment(session, order_id=event.payment.order_id)
    if row is None:
        log.info(
            "payments.webhook_unknown_order",
            webhook_event=event.name,
            order_id=event.payment.order_id,
        )
        return Outcome.UNKNOWN_ORDER
    if event.name == CAPTURED:
        return await _capture(session, row, event)
    if event.name == FAILED:
        return _fail(row, event)
    if event.name in REVERSE:
        return await _reverse(session, row, event)
    if event.name in RESTORE:
        return await _restore(session, row, event)
    return await _settle(session, row, event)


def _fields(row: Payment, event: Event) -> dict[str, str]:
    """What every line about a payment names: never payer data (rule 15)."""
    return {
        "webhook_event": event.name,
        "payment_id": str(row.id),
        "order_id": row.provider_order_id,
    }


async def _capture(session: AsyncSession, row: Payment, event: Event) -> Outcome:
    """Credit a captured payment once (D-026, D-522, D-523)."""
    payment = event.payment
    assert payment is not None
    if row.provider_payment_id is not None:
        if row.provider_payment_id == payment.id:
            log.info("payments.webhook_repeat", **_fields(row, event))
            return Outcome.REPEAT
        log.error(
            "payments.second_capture",
            note="A second payment captured on one order: a duplicate charge, "
            "for T-8.3 to refund. No Velas credited for it.",
            **_fields(row, event),
        )
        return Outcome.SECOND_CAPTURE
    if payment.amount != row.amount_paise or payment.currency != CURRENCY:
        row.status = PaymentStatus.FAILED
        row.raw_webhook = event.raw
        log.error(
            "payments.amount_mismatch",
            note="The gateway's amount or currency isn't the order's: no Velas.",
            **_fields(row, event),
        )
        return Outcome.MISMATCH
    if await repository.owner_gender(session, row.user_id) is not Gender.MALE:
        row.status = PaymentStatus.FAILED
        row.raw_webhook = event.raw
        log.error(
            "payments.not_a_man",
            note="Captured for someone who can't hold Velas (D-076): refund it by hand.",
            **_fields(row, event),
        )
        return Outcome.NOT_A_MAN

    row.status = PaymentStatus.PAID
    row.provider_payment_id = payment.id
    row.paid_at = clock.now()
    row.raw_webhook = event.raw
    await session.flush()
    ref = Ref(RefType.PAYMENT, row.id)
    # The wallet's lock is held from here to the commit (D-077).
    await wallet_service.credit(
        session, row.user_id, row.credits, LedgerReason.PURCHASE, ref=ref
    )
    if row.bonus_credits:
        # Read under the wallet's lock: a capture of his that committed while
        # this one waited for it is seen, so the bonus is granted once (P-380).
        if await repository.bought_other_than(session, row.user_id, row.id):
            row.bonus_credits = 0
            log.info("payments.bonus_withheld", **_fields(row, event))
        else:
            await wallet_service.credit(
                session,
                row.user_id,
                row.bonus_credits,
                LedgerReason.PURCHASE_BONUS,
                ref=ref,
            )
    log.info(
        "payments.captured",
        credits=row.credits,
        bonus_credits=row.bonus_credits,
        **_fields(row, event),
    )
    return Outcome.CAPTURED


# The event a claim's grant is recorded as in `raw_webhook` (T-8.3).
GRANTED_ON_CLAIM: Final = "refund_request.granted"


async def capture_from_gateway(
    session: AsyncSession, row: Payment, payment: ProviderPayment
) -> Outcome:
    """A claim's grant (T-8.3, D-580): the capture the webhook never brought,
    from what the gateway says it holds, through the webhook's own `_capture`,
    so the same reasons, the same key and the same bonus rule (D-077, D-522).
    A webhook that arrives later finds the anchor set: a repeat. The row must
    be locked by the caller. `raw_webhook` keeps the allowlisted fields of the
    gateway's payment, which carries none of the payer's."""
    entity = {
        "id": payment.id,
        "order_id": payment.order_id,
        "amount": payment.amount_paise,
        "currency": payment.currency,
        "status": payment.status,
    }
    event = Event(
        name=CAPTURED,
        payment=PaymentEntity.model_validate(entity),
        raw=raw_webhook(
            {"event": GRANTED_ON_CLAIM, "payload": {"payment": {"entity": entity}}}
        ),
    )
    return await _capture(session, row, event)


def _fail(row: Payment, event: Event) -> Outcome:
    """A failed attempt: never the anchor, so a later capture still credits."""
    if row.status in (PaymentStatus.CREATED, PaymentStatus.FAILED):
        row.status = PaymentStatus.FAILED
        row.raw_webhook = event.raw
        log.info("payments.failed", **_fields(row, event))
        return Outcome.FAILED
    log.info("payments.failed_after_paid", **_fields(row, event))
    return Outcome.UNCHANGED


async def _captured_by(session: AsyncSession, row: Payment, event: Event) -> bool:
    """Whether this event's payment is the one credited on the row, capturing
    it first from the signed payment inside the event if the order isn't
    captured yet (a refund before its capture, D-523)."""
    payment = event.payment
    assert payment is not None
    if row.provider_payment_id is None:
        await _capture(session, row, event)
    if row.provider_payment_id == payment.id:
        return True
    log.warning(
        "payments.not_the_credited_payment",
        note="Money went back on a payment no Velas were credited for: nothing "
        "to take back (a duplicate charge is T-8.3's).",
        **_fields(row, event),
    )
    return False


async def _reverse(session: AsyncSession, row: Payment, event: Event) -> Outcome:
    """Take back what the payment granted, once per refund or dispute (D-520)."""
    if not await _captured_by(session, row, event):
        return Outcome.NOTHING_TO_DO
    outcome = await _reverse_once(session, row, event)
    row.raw_webhook = event.raw
    return outcome


async def _reverse_once(session: AsyncSession, row: Payment, event: Event) -> Outcome:
    other = event.other
    assert other is not None and event.kind is not None
    ref = Ref(RefType.PAYMENT, row.id)
    # Handled already, whatever it took (P-420, D-581): a reversal that took 0
    # wrote no ledger entry, so the record is the check. The ledger's entry
    # still counts for a reversal made before the record existed.
    if await repository.reversal_recorded(
        session, other.id
    ) or await wallet_service.entry_for(
        session, row.user_id, LedgerReason.PURCHASE_REVERSAL, other.id
    ):
        log.info("payments.webhook_repeat", **_fields(row, event))
        return Outcome.REPEAT
    # Never more than the payment granted, less what was taken back for it
    # already: one payment refunded in parts, or refunded and disputed.
    granted = row.credits + row.bonus_credits
    outstanding = granted - await wallet_service.reversed_net(session, row.user_id, ref)
    if outstanding <= 0:
        await repository.record_reversal(
            session,
            payment_id=row.id,
            provider_ref=other.id,
            kind=event.kind,
            taken=0,
            shortfall=0,
        )
        log.info("payments.nothing_to_reverse", **_fields(row, event))
        return Outcome.NOTHING_TO_DO
    reversal = await wallet_service.reverse(
        session,
        row.user_id,
        outstanding,
        LedgerReason.PURCHASE_REVERSAL,
        ref=ref,
        event=other.id,
    )
    await repository.record_reversal(
        session,
        payment_id=row.id,
        provider_ref=other.id,
        kind=event.kind,
        taken=reversal.taken,
        shortfall=reversal.shortfall,
    )
    log.info(
        "payments.reversed",
        taken=reversal.taken,
        shortfall=reversal.shortfall,
        **_fields(row, event),
    )
    if reversal.shortfall:
        log.error(
            "payments.reversal_shortfall",
            note="Money went back for Velas already spent (D-520).",
            shortfall=reversal.shortfall,
            **_fields(row, event),
        )
        if event.kind == "dispute":
            safety_service.record_chargeback_shortfall(
                session, row.user_id, payment_id=row.id, shortfall=reversal.shortfall
            )
    return Outcome.REVERSED


async def _restore(session: AsyncSession, row: Payment, event: Event) -> Outcome:
    """Give back exactly what this refund's or dispute's reversal took, or
    nothing if it took nothing (D-520)."""
    other = event.other
    assert other is not None
    reversal = await wallet_service.entry_for(
        session, row.user_id, LedgerReason.PURCHASE_REVERSAL, other.id
    )
    if reversal is None:
        log.info("payments.nothing_to_restore", **_fields(row, event))
        return Outcome.NOTHING_TO_DO
    restored = await wallet_service.credit(
        session,
        row.user_id,
        -reversal.delta,
        LedgerReason.PURCHASE_RESTORED,
        ref=Ref(RefType.PAYMENT, row.id),
        event=other.id,
    )
    row.raw_webhook = event.raw
    if not restored.applied:
        return Outcome.REPEAT
    log.info("payments.restored", restored=-reversal.delta, **_fields(row, event))
    return Outcome.RESTORED


async def _settle(session: AsyncSession, row: Payment, event: Event) -> Outcome:
    """The money has gone back: `refunded` (D-520). Reversed first if its
    `.created` hasn't arrived, since order isn't guaranteed."""
    if not await _captured_by(session, row, event):
        return Outcome.NOTHING_TO_DO
    await _reverse_once(session, row, event)
    row.raw_webhook = event.raw
    if row.status is PaymentStatus.REFUNDED:
        return Outcome.REPEAT
    row.status = PaymentStatus.REFUNDED
    log.info("payments.refunded", **_fields(row, event))
    return Outcome.REFUNDED
