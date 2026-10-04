"""Two wallet calls at once, on two connections, as two workers would make them
(D-077's layer 4; T-5.4 takes it to fifty, in test_concurrency.py).

The harness, and what it does and doesn't prove, is `races.py`. Here each
holder waits up to a second for company: with two calls that costs two
seconds and leaves a slow machine plenty of room to bring them together when
the lock is gone.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import LedgerReason
from app.core.errors import AppError
from app.modules.wallet import service
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import LedgerResult
from tests.committed import fresh_man
from tests.modules.wallet.races import Move, Race, ledger_of

COMPANY_WAIT_S = 1.0


@pytest.mark.critical  # D-077 layer 4; 06-TESTING.md #1 at two, before T-5.4's fifty
async def test_two_debits_of_the_whole_balance_take_turns(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two debits of 5 on a balance of 5, for two different threads: one is
    applied, the other finds the balance gone."""
    man = await fresh_man(test_engine, credits=5)
    race = Race(monkeypatch, company_wait_s=COMPANY_WAIT_S)

    def debit_for_a_thread() -> Move:
        thread = Ref(RefType.THREAD, uuid.uuid4())
        return lambda session: service.debit(
            session, man, 5, LedgerReason.THREAD_OPEN, ref=thread
        )

    outcomes = await race.run(test_engine, [debit_for_a_thread(), debit_for_a_thread()])

    assert race.open_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    applied = [o for o in outcomes if isinstance(o, LedgerResult)]
    refused = [o for o in outcomes if not isinstance(o, LedgerResult)]
    assert [r.applied for r in applied] == [True]
    assert len(refused) == 1
    error = refused[0]
    assert isinstance(error, AppError), error
    assert (error.code, error.details) == (
        "INSUFFICIENT_CREDITS",
        {"required": 5, "balance": 0},
    )
    assert await ledger_of(test_engine, man) == (2, 0, 0)


@pytest.mark.critical  # D-077 layer 4; 06-TESTING.md #2 at two
async def test_two_credits_of_one_payment_at_once_apply_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two deliveries of one payment's credit: the second, let in after the
    first commits, finds its entry and returns it, applied=False."""
    man = await fresh_man(test_engine)
    race = Race(monkeypatch, company_wait_s=COMPANY_WAIT_S)
    payment = Ref(RefType.PAYMENT, uuid.uuid4())

    def credit_the_payment(session: AsyncSession) -> Awaitable[LedgerResult]:
        return service.credit(session, man, 25, LedgerReason.PURCHASE, ref=payment)

    outcomes = await race.run(test_engine, [credit_the_payment] * 2)

    assert race.open_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    assert all(isinstance(o, LedgerResult) for o in outcomes), outcomes
    results: list[Any] = sorted(outcomes, key=lambda r: not r.applied)
    assert [r.applied for r in results] == [True, False]
    assert results[0].entry.id == results[1].entry.id
    assert await ledger_of(test_engine, man) == (1, 25, 25)
