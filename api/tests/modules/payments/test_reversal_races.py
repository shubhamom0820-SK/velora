"""One refund delivered five times at once (P-420, T-8.3), on connections of
their own with rows committed for real, the overlap forced and asserted at the
payment row's lock (`races.RowRace`).

His Velas are all spent, so the reversal takes 0 and writes no ledger entry:
the only thing that can make the other four a repeat is the refund's record
(`payment_reversals`). The man is fresh and never deleted; his payment and its
record are taken back at the end (`tests/committed.py`).
"""

from __future__ import annotations

import json
import uuid
from collections import Counter

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import LedgerReason
from app.core.providers.payments import FakePayments
from app.modules.payments import webhooks
from app.modules.payments.models import Payment, PaymentReversal
from app.modules.payments.webhooks import Outcome
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType
from tests.committed import fresh_man, take_back_payments
from tests.modules.payments.races import RowRace
from tests.modules.payments.support import captured, new_key, refund
from tests.modules.wallet.races import ledger_of

pytestmark = pytest.mark.usefixtures("test_redis")


async def _paid_and_spent(engine: AsyncEngine, man: uuid.UUID) -> Payment:
    """A pack-30 order, captured (30 and the bonus 6), then all 36 spent."""
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
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
    async with AsyncSession(engine, expire_on_commit=False) as session:
        event = webhooks.read(json.dumps(captured(payment.provider_order_id)).encode())
        async with session.begin():
            assert await webhooks.apply(session, event) is Outcome.CAPTURED
        async with session.begin():
            await wallet_service.debit(
                session,
                man,
                36,
                LedgerReason.THREAD_OPEN,
                ref=Ref(RefType.THREAD, uuid.uuid4()),
            )
    return payment


@pytest.mark.critical
async def test_a_refund_that_takes_nothing_delivered_five_times_at_once_is_handled_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    man = await fresh_man(test_engine)
    payment = await _paid_and_spent(test_engine, man)
    gateway = FakePayments()
    # An id of its own: a committed record outlives a run whose clean-up
    # failed, and must never be another test's refund.
    signed = gateway.sign(
        refund(
            "refund.created",
            payment.provider_order_id,
            refund_id=f"rfnd_race_{uuid.uuid4().hex[:12]}",
        )
    )
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
        assert Counter(outcomes) == {Outcome.REVERSED: 1, Outcome.REPEAT: 4}
        async with AsyncSession(test_engine) as session:
            records = (
                await session.execute(
                    select(PaymentReversal.taken, PaymentReversal.shortfall).where(
                        PaymentReversal.payment_id == payment.id
                    )
                )
            ).all()
        assert [tuple(r) for r in records] == [(0, 36)]
        # The purchase, the bonus and the spend: no reversal entry, balance 0.
        assert await ledger_of(test_engine, man) == (3, 0, 0)
    finally:
        await take_back_payments(test_engine, [payment.id])
