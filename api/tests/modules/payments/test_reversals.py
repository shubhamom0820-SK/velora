"""Refunds and disputes made outside us (T-8.2, D-076 rule 3, D-520): money
that goes back takes its Velas back in the same step, what the balance holds,
down to 0; a refund that fails or a dispute that is won gives back exactly what
was taken; the status is `refunded` only once the money has gone."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import LedgerReason, PaymentStatus
from app.core.providers import FakeProviders
from app.modules.payments import rules, service
from app.modules.payments.models import Payment, PaymentReversal
from app.modules.safety.models import FraudEvent
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import Ref, RefType
from tests.conftest import CapturedLogs, MakeUser
from tests.grants import grant
from tests.modules.payments.support import captured, deliver, dispute, order, refund

pytestmark = pytest.mark.usefixtures("test_redis")

PURCHASE, BONUS = LedgerReason.PURCHASE, LedgerReason.PURCHASE_BONUS
REVERSAL, RESTORED = LedgerReason.PURCHASE_REVERSAL, LedgerReason.PURCHASE_RESTORED


async def _row(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    row = await db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def _moves(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Any, int]]:
    """His entries since the purchase, by reason, in the order they were made
    (one per transaction here, so `created_at` orders them)."""
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta)
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at, LedgerEntry.reason)
    )
    return [tuple(row) for row in rows]


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return int(balance or 0)


async def _signals(db: AsyncSession, user_id: uuid.UUID) -> list[FraudEvent]:
    return list(
        (
            await db.scalars(select(FraudEvent).where(FraudEvent.user_id == user_id))
        ).all()
    )


async def _paid(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, payments: Any
) -> tuple[User, uuid.UUID, str]:
    """A man whose pack-30 is paid: 30 Velas and the first-purchase 6."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    await deliver(client, payments, captured(order_id))
    assert await _balance(db, man.id) == 36
    return man, payment_id, order_id


async def _spend(db: AsyncSession, man: User, credits: int) -> None:
    """Velas spent, as a Thread opened spends them, in the test's transaction
    (begun by the read, as a request's statements begin one)."""
    await _balance(db, man.id)
    await wallet_service.debit(
        db,
        man.id,
        credits,
        LedgerReason.THREAD_OPEN,
        ref=Ref(RefType.THREAD, uuid.uuid4()),
    )


async def _grant(db: AsyncSession, man: User, credits: int) -> None:
    await _balance(db, man.id)
    await grant(db, man.id, credits, event="another-purchase")


# --- Refunds --------------------------------------------------------------------------


async def test_a_refund_created_takes_the_velas_back_and_the_status_stays_paid(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """At `refund.created`, the moment the money is committed to go back,
    never days later at `.processed` (D-520)."""
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )

    response = await deliver(
        client, fake_providers.payments, refund("refund.created", order_id)
    )

    assert response.status_code == 200
    assert await _balance(db, man.id) == 0
    assert (REVERSAL, -36) in await _moves(db, man.id)
    row = await _row(db, payment_id)
    assert row.status is PaymentStatus.PAID
    assert row.raw_webhook is not None
    assert row.raw_webhook["refund"]["id"] == "rfnd_test_1"


async def test_a_refund_processed_marks_it_refunded(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await deliver(client, fake_providers.payments, refund("refund.created", order_id))

    await deliver(client, fake_providers.payments, refund("refund.processed", order_id))

    assert (await _row(db, payment_id)).status is PaymentStatus.REFUNDED
    assert [m for m in await _moves(db, man.id) if m[0] is REVERSAL] == [
        (REVERSAL, -36)
    ]


async def test_a_failed_refund_gives_back_what_it_took(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await deliver(client, fake_providers.payments, refund("refund.created", order_id))

    await deliver(client, fake_providers.payments, refund("refund.failed", order_id))

    assert await _balance(db, man.id) == 36
    assert (RESTORED, 36) in await _moves(db, man.id)
    assert (await _row(db, payment_id)).status is PaymentStatus.PAID


async def test_the_same_refund_twice_reverses_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, _, order_id = await _paid(db, client, make_user, fake_providers.payments)
    for _ in range(2):
        await deliver(
            client, fake_providers.payments, refund("refund.created", order_id)
        )

    assert [m for m in await _moves(db, man.id) if m[0] is REVERSAL] == [
        (REVERSAL, -36)
    ]


async def test_a_restore_with_no_reversal_gives_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, _, order_id = await _paid(db, client, make_user, fake_providers.payments)

    await deliver(client, fake_providers.payments, refund("refund.failed", order_id))

    assert await _balance(db, man.id) == 36
    assert {m[0] for m in await _moves(db, man.id)} == {PURCHASE, BONUS}


async def test_two_refunds_of_one_payment_never_take_more_than_it_granted(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Refunded in two parts, with Velas from another purchase beside it: the
    second refund finds nothing of this payment's left to take."""
    man, _, order_id = await _paid(db, client, make_user, fake_providers.payments)
    await _grant(db, man, 50)

    for refund_id in ("rfnd_part_1", "rfnd_part_2"):
        await deliver(
            client,
            fake_providers.payments,
            refund("refund.created", order_id, refund_id=refund_id),
        )

    assert await _balance(db, man.id) == 50
    assert [m for m in await _moves(db, man.id) if m[0] is REVERSAL] == [
        (REVERSAL, -36)
    ]


# --- Disputes ---------------------------------------------------------------------------


async def test_a_dispute_reverses_then_a_win_restores(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Taken at `.created`, though Razorpay deducts the money only if it's
    lost: he can't spend Velas through a dispute that lasts weeks (D-520)."""
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )

    await deliver(
        client, fake_providers.payments, dispute("payment.dispute.created", order_id)
    )
    assert await _balance(db, man.id) == 0
    assert (await _row(db, payment_id)).status is PaymentStatus.PAID

    await deliver(
        client, fake_providers.payments, dispute("payment.dispute.won", order_id)
    )

    assert await _balance(db, man.id) == 36
    assert (await _row(db, payment_id)).status is PaymentStatus.PAID


async def test_a_dispute_lost_marks_it_refunded(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await deliver(
        client, fake_providers.payments, dispute("payment.dispute.created", order_id)
    )

    await deliver(
        client, fake_providers.payments, dispute("payment.dispute.lost", order_id)
    )

    assert (await _row(db, payment_id)).status is PaymentStatus.REFUNDED
    assert await _balance(db, man.id) == 0


@pytest.mark.parametrize(
    "name",
    [
        "payment.dispute.closed",
        "payment.dispute.under_review",
        "payment.dispute.action_required",
    ],
)
async def test_the_other_dispute_events_change_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    name: str,
) -> None:
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )

    response = await deliver(client, fake_providers.payments, dispute(name, order_id))

    assert response.status_code == 200
    assert await _balance(db, man.id) == 36
    assert (await _row(db, payment_id)).status is PaymentStatus.PAID


# --- Velas already spent (D-520) -------------------------------------------------------


@pytest.mark.critical
@pytest.mark.parametrize("kind", ["refund", "dispute"])
async def test_velas_partly_spent_take_what_is_left_and_record_the_rest(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
    kind: str,
) -> None:
    """Of 36, 26 spent: the 10 left are taken, the balance stops at 0, and the
    26 are a shortfall, logged; on a dispute a `chargeback_shortfall` signal
    too, worth 30 since T-9.2 (D-900)."""
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await _spend(db, man, 26)
    created = (
        refund("refund.created", order_id)
        if kind == "refund"
        else dispute("payment.dispute.created", order_id)
    )

    await deliver(client, fake_providers.payments, created)

    assert await _balance(db, man.id) == 0
    assert (REVERSAL, -10) in await _moves(db, man.id)
    [line] = [
        e
        for e in captured_logs.events
        if e.get("event") == "payments.reversal_shortfall"
    ]
    assert (line["log_level"], line["shortfall"]) == ("error", 26)
    signals = await _signals(db, man.id)
    if kind == "refund":
        assert signals == []
    else:
        [signal] = signals
        assert (signal.signal, signal.weight) == ("chargeback_shortfall", 30)
        assert signal.meta is not None
        assert (signal.meta["payment_id"], signal.meta["shortfall"]) == (
            str(payment_id),
            26,
        )


async def test_a_restore_after_a_partial_reversal_gives_back_only_what_was_taken(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, _, order_id = await _paid(db, client, make_user, fake_providers.payments)
    await _spend(db, man, 26)
    await deliver(client, fake_providers.payments, refund("refund.created", order_id))

    await deliver(client, fake_providers.payments, refund("refund.failed", order_id))

    assert await _balance(db, man.id) == 10
    assert (RESTORED, 10) in await _moves(db, man.id)


async def test_velas_spent_entirely_take_nothing_and_record_the_shortfall(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await _spend(db, man, 36)

    await deliver(
        client, fake_providers.payments, dispute("payment.dispute.created", order_id)
    )

    assert await _balance(db, man.id) == 0
    assert REVERSAL not in {m[0] for m in await _moves(db, man.id)}
    [signal] = await _signals(db, man.id)
    assert signal.meta is not None
    assert (signal.meta["payment_id"], signal.meta["shortfall"]) == (
        str(payment_id),
        36,
    )
    assert [
        e["shortfall"]
        for e in captured_logs.events
        if e.get("event") == "payments.reversal_shortfall"
    ] == [36]


# --- Each refund or dispute is handled once, whatever it took (P-420, D-581) ------------


async def _records(db: AsyncSession, payment_id: uuid.UUID) -> list[tuple[Any, ...]]:
    rows = await db.execute(
        select(
            PaymentReversal.provider_ref,
            PaymentReversal.kind,
            PaymentReversal.taken,
            PaymentReversal.shortfall,
        )
        .where(PaymentReversal.payment_id == payment_id)
        .order_by(PaymentReversal.provider_ref)
    )
    return [tuple(row) for row in rows]


@pytest.mark.critical
@pytest.mark.parametrize("kind", ["refund", "dispute"])
async def test_a_reversal_that_took_nothing_never_takes_velas_bought_since(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    kind: str,
) -> None:
    """P-420's worst case. He spends all 36, so the refund or dispute takes 0
    and writes no ledger entry. He buys 30 more. Razorpay redelivers that same
    event: it is a repeat, by its record, and his 30 stay; a dispute's signal
    is recorded once."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    await deliver(client, fake_providers.payments, captured(order_id))
    await _spend(db, man, 36)
    created = (
        refund("refund.created", order_id)
        if kind == "refund"
        else dispute("payment.dispute.created", order_id)
    )
    await deliver(client, fake_providers.payments, created)
    assert await _balance(db, man.id) == 0
    _, second_order = await order(client, token, "pack-30")
    await deliver(client, fake_providers.payments, captured(second_order))
    assert await _balance(db, man.id) == 30

    response = await deliver(client, fake_providers.payments, created)

    assert response.status_code == 200
    assert await _balance(db, man.id) == 30
    assert REVERSAL not in {m[0] for m in await _moves(db, man.id)}
    ref = "rfnd_test_1" if kind == "refund" else "disp_test_1"
    assert await _records(db, payment_id) == [(ref, kind, 0, 36)]
    assert len(await _signals(db, man.id)) == (1 if kind == "dispute" else 0)


async def test_every_refund_handled_is_recorded_with_what_it_took(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """26 of 36 spent: the refund takes 10, short 26. A dispute of the payment
    reversed in full finds nothing outstanding and is recorded too, 0 and 0."""
    man, payment_id, order_id = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await _spend(db, man, 26)
    await deliver(client, fake_providers.payments, refund("refund.created", order_id))
    other, other_payment, other_order = await _paid(
        db, client, make_user, fake_providers.payments
    )
    await deliver(
        client,
        fake_providers.payments,
        refund("refund.created", other_order, refund_id="rfnd_other_1"),
    )
    await _grant(db, other, 50)

    await deliver(
        client, fake_providers.payments, dispute("payment.dispute.created", other_order)
    )

    assert await _records(db, payment_id) == [("rfnd_test_1", "refund", 10, 26)]
    # One test transaction: every row shares `created_at`, so by Razorpay id.
    assert sorted(await _records(db, other_payment)) == [
        ("disp_test_1", "dispute", 0, 0),
        ("rfnd_other_1", "refund", 36, 0),
    ]
    assert await _balance(db, other.id) == 50


# --- Out of order -------------------------------------------------------------------------


@pytest.mark.critical
@pytest.mark.parametrize("first", ["refund.created", "refund.processed"])
async def test_a_refund_before_its_capture_captures_then_reverses(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    first: str,
) -> None:
    """Razorpay doesn't promise order: the refund's own signed payment is
    captured first, then reversed, net 0; the capture that comes later is a
    repeat."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)

    await deliver(client, fake_providers.payments, refund(first, order_id))

    row = await _row(db, payment_id)
    assert row.provider_payment_id == f"pay_for_{order_id}"
    assert row.status is (
        PaymentStatus.REFUNDED if first == "refund.processed" else PaymentStatus.PAID
    )
    assert await _balance(db, man.id) == 0
    assert sorted(await _moves(db, man.id)) == sorted(
        [(PURCHASE, 30), (BONUS, 6), (REVERSAL, -36)]
    )

    await deliver(client, fake_providers.payments, captured(order_id))

    assert await _balance(db, man.id) == 0
    assert len(await _moves(db, man.id)) == 3


async def test_a_refund_of_another_payment_on_the_order_takes_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """A duplicate charge refunded (T-8.3's case): its Velas were never
    credited, so none are taken."""
    man, _, order_id = await _paid(db, client, make_user, fake_providers.payments)

    await deliver(
        client,
        fake_providers.payments,
        refund("refund.created", order_id, payment_id="pay_duplicate"),
    )

    assert await _balance(db, man.id) == 36


# --- Turnover follows the money (D-483) ---------------------------------------------------


@pytest.mark.critical
async def test_turnover_drops_a_refund_and_keeps_a_dispute_not_yet_lost(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    year = rules.financial_year_of(clock.now())
    before = await service.turnover(db, year)
    _, _, refunded = await _paid(db, client, make_user, fake_providers.payments)
    _, _, disputed = await _paid(db, client, make_user, fake_providers.payments)

    for body in (
        refund("refund.created", refunded),
        refund("refund.processed", refunded),
        dispute("payment.dispute.created", disputed),
    ):
        await deliver(client, fake_providers.payments, body)

    after = await service.turnover(db, year)
    assert after.paid_payments - before.paid_payments == 1
    assert after.turnover_paise - before.turnover_paise == 150_000
