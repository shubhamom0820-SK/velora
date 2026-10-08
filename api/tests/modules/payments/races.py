"""Webhooks delivered at once, each in a transaction of its own on a
connection of its own, as Razorpay's retries and our workers would make them
(T-8.2), and what the payment row's lock decided. `tests/modules/wallet/races.py`
does the same at the wallet's lock; this is its counterpart at the row's.

- **Every delivery is inside its transaction, at the lock, before any is let
  through to it.** Each counts itself in as it arrives (`at_lock`) and waits for
  the rest: that is the forced overlap, proved rather than trusted to `gather`.
- **After its locked read, each waits up to `company_wait_s` for another to be
  holding a row too,** and records whether it waited alone. With the lock nobody
  gets past the read until the holder commits, so every delivery waits alone.
  Without it they meet, and none does.

A red without the lock depends on the scheduler (P-58), so a breaking run is
reported as red in N of N. Rows are committed for real: the payments are taken
back at the end (`tests/committed.py`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.payments import repository
from app.modules.payments.models import Payment

ARRIVE_WAIT_S = 10.0

Delivery = Callable[[AsyncSession], Awaitable[object]]


class RowRace:
    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, *, calls: int, company_wait_s: float
    ) -> None:
        self.calls = calls
        self.company_wait_s = company_wait_s
        self.arrived = 0
        self.all_arrived = asyncio.Event()
        self.at_lock: list[tuple[int, bool]] = []
        self.holding: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real_lock = repository.lock_payment

        async def arrive_lock_then_wait_for_company(
            session: AsyncSession, **by: str | None
        ) -> Payment | None:
            self.arrived += 1
            if self.arrived == self.calls:
                self.all_arrived.set()
            await asyncio.wait_for(self.all_arrived.wait(), ARRIVE_WAIT_S)
            self.at_lock.append((self.arrived, session.in_transaction()))
            locked = await real_lock(session, **by)
            me = id(session)
            self.holding.add(me)
            if len(self.holding) > 1:
                self.company.set()
            try:
                await asyncio.wait_for(self.company.wait(), self.company_wait_s)
            except TimeoutError:
                self.waited_alone.append(True)
            else:
                self.waited_alone.append(False)
            self.holding.discard(me)
            return locked

        monkeypatch.setattr(
            repository, "lock_payment", arrive_lock_then_wait_for_company
        )

    async def run(
        self, engine: AsyncEngine, deliveries: Sequence[Delivery]
    ) -> list[object]:
        """Each delivery on a fresh session from the engine's pool; each opens
        its own transaction, as the route's does."""
        assert len(deliveries) == self.calls

        async def attempt(delivery: Delivery) -> object:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                try:
                    return await delivery(session)
                except Exception as error:  # noqa: BLE001 — the test reads it
                    return error

        return list(await asyncio.gather(*(attempt(d) for d in deliveries)))

    def assert_every_delivery_overlapped_and_waited_alone(self) -> None:
        assert self.at_lock == [(self.calls, True)] * self.calls
        assert self.waited_alone == [True] * self.calls
