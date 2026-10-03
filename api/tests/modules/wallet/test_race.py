"""Two wallet calls at once, on two connections, as two workers would make them
(D-077's layer 4; T-5.4 takes it to fifty).

What is asserted is what the lock decides, never the order the event loop
happens to resume the two in (`f543b0d`):

- **Both are inside open transactions before either takes the lock**, and each
  checks that at the moment it asks for the lock. That is the forced overlap,
  and the test proves it happened rather than trusting `gather` to arrange it.
- **After its locked read, each waits up to `COMPANY_WAIT_S` for the other to
  be holding the wallet too**, and records whether it waited alone. With the
  lock the other can't get past its read until this one commits, so both wait
  alone. Without it they meet, and neither does. A slow machine can only make
  the wait longer, never turn a missing lock green.

Committed for real, so on fresh men, never deleted, every assertion scoped to
them (tests/committed.py).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import Gender, LedgerReason
from app.core.errors import AppError
from app.modules.wallet import repository, service
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import LedgerResult
from tests.committed import fresh_man

COMPANY_WAIT_S = 1.0
OPEN_WAIT_S = 5.0

Move = Callable[[AsyncSession], Awaitable[LedgerResult]]


class Race:
    """Two moves on one wallet, each in its own session and transaction."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opened = 0
        self.all_open = asyncio.Event()
        self.open_at_lock: list[int] = []
        self.holding: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real_lock = repository.lock_wallet

        async def lock_then_wait_for_company(
            session: AsyncSession, user_id: uuid.UUID
        ) -> tuple[int, Gender | None] | None:
            self.open_at_lock.append(self.opened)
            locked = await real_lock(session, user_id)
            me = id(session)
            self.holding.add(me)
            if len(self.holding) > 1:
                self.company.set()
            try:
                await asyncio.wait_for(self.company.wait(), timeout=COMPANY_WAIT_S)
            except TimeoutError:
                self.waited_alone.append(True)
            else:
                self.waited_alone.append(False)
            self.holding.discard(me)
            return locked

        monkeypatch.setattr(repository, "lock_wallet", lock_then_wait_for_company)

    async def run(
        self, engine: AsyncEngine, user_id: uuid.UUID, moves: list[Move]
    ) -> list[LedgerResult | Exception]:
        async def attempt(move: Move) -> LedgerResult | Exception:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                try:
                    async with session.begin():
                        # A query opens the transaction on the server, and puts
                        # the wallet in the session as it was before the race:
                        # a lock that read it from there would read it stale.
                        await session.get(Wallet, user_id)
                        self.opened += 1
                        if self.opened == len(moves):
                            self.all_open.set()
                        await asyncio.wait_for(self.all_open.wait(), OPEN_WAIT_S)
                        return await move(session)
                except Exception as error:  # noqa: BLE001 — the test reads it
                    return error

        return list(await asyncio.gather(*(attempt(move) for move in moves)))


async def _ledger(engine: AsyncEngine, user_id: uuid.UUID) -> tuple[int, int, int]:
    """(entries, their sum, the balance), his alone."""
    async with AsyncSession(engine) as session:
        count, total = (
            await session.execute(
                select(
                    func.count(), func.coalesce(func.sum(LedgerEntry.delta), 0)
                ).where(LedgerEntry.user_id == user_id)
            )
        ).one()
        balance = await session.scalar(
            select(Wallet.balance).where(Wallet.user_id == user_id)
        )
    return int(count), int(total), int(balance or 0)


@pytest.mark.critical  # D-077 layer 4; 06-TESTING.md #1 at two, before T-5.4's fifty
async def test_two_debits_of_the_whole_balance_take_turns(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two debits of 5 on a balance of 5, for two different threads: one is
    applied, the other finds the balance gone."""
    man = await fresh_man(test_engine, credits=5)
    race = Race(monkeypatch)

    def debit_for_a_thread() -> Move:
        thread = Ref(RefType.THREAD, uuid.uuid4())
        return lambda session: service.debit(
            session, man, 5, LedgerReason.THREAD_OPEN, ref=thread
        )

    outcomes = await race.run(
        test_engine, man, [debit_for_a_thread(), debit_for_a_thread()]
    )

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
    assert await _ledger(test_engine, man) == (2, 0, 0)


@pytest.mark.critical  # D-077 layer 4; 06-TESTING.md #2 at two
async def test_two_credits_of_one_payment_at_once_apply_once(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two deliveries of one payment's credit: the second, let in after the
    first commits, finds its entry and returns it, applied=False."""
    man = await fresh_man(test_engine)
    race = Race(monkeypatch)
    payment = Ref(RefType.PAYMENT, uuid.uuid4())

    def credit_the_payment(session: AsyncSession) -> Awaitable[LedgerResult]:
        return service.credit(session, man, 25, LedgerReason.PURCHASE, ref=payment)

    outcomes = await race.run(test_engine, man, [credit_the_payment] * 2)

    assert race.open_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    assert all(isinstance(o, LedgerResult) for o in outcomes), outcomes
    results: list[Any] = sorted(outcomes, key=lambda r: not r.applied)
    assert [r.applied for r in results] == [True, False]
    assert results[0].entry.id == results[1].entry.id
    assert await _ledger(test_engine, man) == (1, 25, 25)
