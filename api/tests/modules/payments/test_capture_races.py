"""Captures at once (T-8.2), on connections of their own with rows committed
for real, the overlap forced and asserted:

- one webhook delivered five times at once is credited once, decided at the
  payment row's lock (`races.RowRace`);
- two orders of one man captured at once grant the first-purchase bonus once,
  decided at the wallet's lock (`tests/modules/wallet/races.py`, P-380, D-522).

The men are fresh and never deleted; their payments are taken back at the end
(`tests/committed.py`), and every assertion is scoped to them.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import LedgerReason, PaymentStatus
from app.core.providers.payments import FakePayments
from app.modules.payments import webhooks
from app.modules.payments.models import Payment
from app.modules.payments.webhooks import Outcome
from app.modules.wallet.models import LedgerEntry
from tests.committed import fresh_man, take_back_payments
from tests.modules.payments.races import RowRace
from tests.modules.payments.support import captured, new_key
from tests.modules.wallet.races import Move, Race, ledger_of

pytestmark = pytest.mark.usefixtures("test_redis")


async def _committed_order(engine: AsyncEngine, man: uuid.UUID) -> Payment:
    """A pack-30 order, `created`, first-purchase bonus 6, committed."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            payment = Payment(
                user_id=man,
                pack_id="pack-30",
                amount_paise=150_000,
                credits=30,
                bonus_credits=6,
                idempotency_key=new_key(),
                provider_order_id=f"order_race_{uuid.uuid4().hex}",
            )
            session.add(payment)
        return payment


async def _reasons(engine: AsyncEngine, man: uuid.UUID) -> Counter[LedgerReason]:
    async with AsyncSession(engine) as session:
        return Counter(
            await session.scalars(
                select(LedgerEntry.reason).where(LedgerEntry.user_id == man)
            )
        )


async def _status(engine: AsyncEngine, payment_id: uuid.UUID) -> Payment:
    async with AsyncSession(engine) as session:
        row = await session.get(Payment, payment_id)
        assert row is not None
        return row


@pytest.mark.critical
async def test_one_webhook_delivered_five_times_at_once_is_credited_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Razorpay redelivers by design. All five are in their transactions at
    the row's lock before any gets it; each then waits alone, so the lock
    decided; one captures, four find the anchor set."""
    man = await fresh_man(test_engine)
    payment = await _committed_order(test_engine, man)
    gateway = FakePayments()
    signed = gateway.sign(captured(payment.provider_order_id))
    race = RowRace(monkeypatch, calls=5, company_wait_s=0.5)
    try:
        outcomes = await race.run(
            test_engine,
            [
                lambda session: webhooks.receive(
                    session, gateway, signed.body, signed.signature
                )
            ]
            * 5,
        )

        race.assert_every_delivery_overlapped_and_waited_alone()
        assert Counter(outcomes) == {Outcome.CAPTURED: 1, Outcome.REPEAT: 4}
        assert await ledger_of(test_engine, man) == (2, 36, 36)
        row = await _status(test_engine, payment.id)
        assert row.status is PaymentStatus.PAID
    finally:
        await take_back_payments(test_engine, [payment.id])


@pytest.mark.critical
async def test_two_orders_captured_at_once_grant_the_bonus_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P-380: both ordered before either was paid, so both rows carry the
    bonus. Both are in their transactions before either asks for the wallet;
    the second capture reads the first's, committed, under the wallet's lock,
    and grants none."""
    man = await fresh_man(test_engine)
    first = await _committed_order(test_engine, man)
    second = await _committed_order(test_engine, man)
    events = [
        webhooks.read(json.dumps(captured(p.provider_order_id)).encode())
        for p in (first, second)
    ]
    race = Race(monkeypatch, company_wait_s=1.0)
    try:

        def capture(event: webhooks.Event) -> Move:
            # The race reads only what the lock decided: what a move returns
            # is checked for an exception and nothing else.
            return cast(Move, lambda session: webhooks.apply(session, event))

        outcomes = await race.run(test_engine, [capture(e) for e in events])

        assert [str(outcome) for outcome in outcomes] == ["captured", "captured"]
        # Two purchases and the one bonus each asked for the wallet, all three
        # with both transactions open, and each waited alone at it.
        assert race.open_at_lock == [2, 2, 2]
        assert race.waited_alone == [True, True, True]
        assert await _reasons(test_engine, man) == {
            LedgerReason.PURCHASE: 2,
            LedgerReason.PURCHASE_BONUS: 1,
        }
        assert await ledger_of(test_engine, man) == (3, 66, 66)
        bonuses = sorted(
            [(await _status(test_engine, p.id)).bonus_credits for p in (first, second)]
        )
        assert bonuses == [0, 6]
    finally:
        await take_back_payments(test_engine, [first.id, second.id])
