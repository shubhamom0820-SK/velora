"""Two admins resolve one claim at once (T-8.3, D-580), on connections of their
own with rows committed for real, the overlap forced and asserted at the
claim's lock.

Both are in their transactions, at the lock, before either is let through to
it. After its locked read, each waits up to `COMPANY_WAIT_S` for the other to be
holding the claim too: with the lock nobody gets past the read until the
holder commits, so each waits alone; without it they meet. The one that waited
finds the claim resolved, `NOT_ALLOWED`, and the gateway is asked for one
refund. Without the lock the second would ask the gateway again, and only
Razorpay's own receipt rule would stop it: a `PROVIDER_UNAVAILABLE`, not ours.

The men are fresh and never deleted; the payment and its claim are taken back
at the end (`tests/committed.py`).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import PaymentStatus
from app.core.errors import AppError
from app.core.providers.payments import FakePayments, ProviderPayment
from app.modules.payments import claims, repository
from app.modules.payments.models import Payment, RefundRequest
from app.modules.payments.rules import ClaimAction
from app.modules.payments.schemas import AdminRefundRequest
from tests.committed import fresh_man, take_back_payments
from tests.modules.payments.support import new_key

pytestmark = pytest.mark.usefixtures("test_redis")

ARRIVE_WAIT_S = 10.0
COMPANY_WAIT_S = 0.5


async def _charged_twice(engine: AsyncEngine, man: uuid.UUID) -> tuple[Payment, str]:
    """A credited payment, a second capture on its order, and his claim."""
    order_id = f"order_race_{uuid.uuid4().hex}"
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        payment = Payment(
            user_id=man,
            pack_id="pack-30",
            amount_paise=150_000,
            credits=30,
            idempotency_key=new_key(),
            provider_order_id=order_id,
            provider_payment_id=f"pay_credited_{uuid.uuid4().hex[:8]}",
            status=PaymentStatus.PAID,
            paid_at=datetime(2026, 10, 8, 6, 0, tzinfo=UTC),
        )
        session.add(payment)
        await session.flush()
        claim = RefundRequest(
            user_id=man, payment_id=payment.id, reason="duplicate_charge"
        )
        session.add(claim)
    return payment, str(claim.id)


@pytest.mark.critical
async def test_two_admins_resolving_one_claim_at_once_refund_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    man = await fresh_man(test_engine)
    admin = await fresh_man(test_engine)
    payment, claim_id = await _charged_twice(test_engine, man)
    assert payment.provider_payment_id is not None
    gateway = FakePayments()
    gateway.payments[payment.provider_order_id] = [
        ProviderPayment(
            id=payment.provider_payment_id,
            order_id=payment.provider_order_id,
            amount_paise=150_000,
            currency="INR",
            status="captured",
        ),
        ProviderPayment(
            id="pay_second",
            order_id=payment.provider_order_id,
            amount_paise=150_000,
            currency="INR",
            status="captured",
        ),
    ]
    refunds_asked = 0
    real_refund = gateway.refund

    async def counted_refund(**asked: object) -> object:
        nonlocal refunds_asked
        refunds_asked += 1
        return await real_refund(**asked)  # type: ignore[arg-type]

    monkeypatch.setattr(gateway, "refund", counted_refund)

    arrived = 0
    all_arrived = asyncio.Event()
    holding: set[int] = set()
    company = asyncio.Event()
    in_transaction: list[bool] = []
    waited_alone: list[bool] = []
    real_lock = repository.lock_claim

    async def arrive_then_wait_for_company(
        session: AsyncSession, claim: uuid.UUID
    ) -> RefundRequest | None:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            all_arrived.set()
        await asyncio.wait_for(all_arrived.wait(), ARRIVE_WAIT_S)
        in_transaction.append(session.in_transaction())
        locked = await real_lock(session, claim)
        me = id(session)
        holding.add(me)
        if len(holding) > 1:
            company.set()
        try:
            await asyncio.wait_for(company.wait(), COMPANY_WAIT_S)
        except TimeoutError:
            waited_alone.append(True)
        else:
            waited_alone.append(False)
        holding.discard(me)
        return locked

    monkeypatch.setattr(repository, "lock_claim", arrive_then_wait_for_company)

    async def attempt() -> object:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            try:
                return await claims.resolve(
                    session,
                    gateway,
                    admin,
                    uuid.UUID(claim_id),
                    ClaimAction.REFUND,
                    None,
                )
            except Exception as error:  # noqa: BLE001 — the test reads it
                return error

    tasks = [asyncio.ensure_future(attempt()) for _ in range(2)]
    try:
        async with asyncio.timeout(30):
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        assert in_transaction == [True, True]
        assert waited_alone == [True, True]
        resolved = [o for o in outcomes if isinstance(o, AdminRefundRequest)]
        refused = [o for o in outcomes if isinstance(o, AppError)]
        assert len(resolved) == 1, outcomes
        assert [(e.code, e.details) for e in refused] == [
            ("NOT_ALLOWED", {"why": "resolved"})
        ]
        assert resolved[0].provider_payment_id == "pay_second"
        assert refunds_asked == 1
        assert len(gateway.refunds) == 1
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await take_back_payments(test_engine, [payment.id])
