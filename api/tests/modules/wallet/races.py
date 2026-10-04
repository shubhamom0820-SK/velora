"""Wallet calls made at once, each in a transaction of its own on a connection
of its own, as workers would make them, and what the wallet's lock decided
(D-077's layer 4; T-5.1 with two calls, T-5.4 with fifty).

What is asserted is what the lock decides, never the order the event loop
happens to resume calls in (`f543b0d`):

- **Every call is inside an open transaction before any asks for the lock.**
  Each records, as it asks, how many are open (`open_at_lock`). That is the
  forced overlap, proved rather than trusted to `gather`.
- **After its locked read, each waits up to `company_wait_s` for another call
  to be holding the same wallet,** and records whether it waited alone. With
  the lock nobody gets past the read until the holder commits, so every call
  waits alone. Without it they meet, and none does.

The limit (P-58): a green is the lock's word, but a red without the lock
depends on the scheduler; the calls must reach their reads inside each other's
wait. So a breaking run is reported as red in N of N, never just "red".

Rows are committed for real: on fresh men, never deleted, every assertion
scoped to them (tests/committed.py).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core.enums import Gender
from app.modules.wallet import repository
from app.modules.wallet.models import LedgerEntry, Wallet
from app.modules.wallet.service import LedgerResult

OPEN_WAIT_S = 10.0

Move = Callable[[AsyncSession], Awaitable[LedgerResult]]
Outcome = LedgerResult | Exception


class Race:
    """Moves on wallets, at once, each in its own session and transaction."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, *, company_wait_s: float
    ) -> None:
        self.company_wait_s = company_wait_s
        self.calls = 0
        self.opened = 0
        self.all_open = asyncio.Event()
        self.open_at_lock: list[int] = []
        self.holding: defaultdict[uuid.UUID, set[int]] = defaultdict(set)
        self.company: defaultdict[uuid.UUID, asyncio.Event] = defaultdict(asyncio.Event)
        self.waited_alone: list[bool] = []
        real_lock = repository.lock_wallet

        async def lock_then_wait_for_company(
            session: AsyncSession, user_id: uuid.UUID
        ) -> tuple[int, Gender | None] | None:
            self.open_at_lock.append(self.opened)
            locked = await real_lock(session, user_id)
            me, holders = id(session), self.holding[user_id]
            holders.add(me)
            if len(holders) > 1:
                self.company[user_id].set()
            try:
                await asyncio.wait_for(
                    self.company[user_id].wait(), timeout=self.company_wait_s
                )
            except TimeoutError:
                self.waited_alone.append(True)
            else:
                self.waited_alone.append(False)
            holders.discard(me)
            return locked

        monkeypatch.setattr(repository, "lock_wallet", lock_then_wait_for_company)

    async def run(self, engine: AsyncEngine, moves: Sequence[Move]) -> list[Outcome]:
        """Each move on a session the engine's pool hands out."""
        sessions = [AsyncSession(engine, expire_on_commit=False) for _ in moves]
        return await self._race(sessions, moves)

    async def run_on(
        self, connections: Sequence[AsyncConnection], moves: Sequence[Move]
    ) -> list[Outcome]:
        """Each move on one of `connections`, one each: so N moves are N
        backends, which the caller has already counted."""
        assert len(connections) == len(moves)
        sessions = [
            AsyncSession(bind=connection, expire_on_commit=False)
            for connection in connections
        ]
        return await self._race(sessions, moves)

    async def _race(
        self, sessions: Sequence[AsyncSession], moves: Sequence[Move]
    ) -> list[Outcome]:
        self.calls = len(moves)

        async def attempt(session: AsyncSession, move: Move) -> Outcome:
            async with session:
                try:
                    async with session.begin():
                        # A query opens the transaction on the server, and
                        # puts the wallets in the session as they were before
                        # the race: a lock that read them from there would
                        # read them stale.
                        await session.scalars(select(Wallet))
                        self.opened += 1
                        if self.opened == self.calls:
                            self.all_open.set()
                        await asyncio.wait_for(self.all_open.wait(), OPEN_WAIT_S)
                        return await move(session)
                except Exception as error:  # noqa: BLE001 — the test reads it
                    return error

        return list(
            await asyncio.gather(*(attempt(s, m) for s, m in zip(sessions, moves)))
        )

    def assert_every_call_overlapped_and_waited_alone(self) -> None:
        assert self.open_at_lock == [self.calls] * self.calls
        assert self.waited_alone == [True] * self.calls


def violated(outcome: Outcome) -> str | None:
    """The constraint a unique violation named, or None for anything else."""
    if not isinstance(outcome, IntegrityError) or outcome.orig is None:
        return None
    name = getattr(outcome.orig.__cause__, "constraint_name", None)
    return name if isinstance(name, str) else None


async def ledger_of(engine: AsyncEngine, user_id: uuid.UUID) -> tuple[int, int, int]:
    """(entries, their sum, the balance): his alone, never the table's."""
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
