"""A double tap opens one Thread and charges once (T-7.1).

Rows are committed for real, on two fresh men who both seek men and share a
committed match (a man can open a Thread with a man; no woman is needed). The
Thread, the match and the notification are taken back at the end, and the men
put back as `fresh_man` left them; the one `thread_open` ledger row stays, as
every fresh man's rows do (06-TESTING, "Tests that commit rows").

The race is forced, never trusted to `gather` (concurrency-tests-must-prove-overlap):
both opens are inside open transactions before either asks for the pair's
lock, and each, holding it, waits for the other to hold it too. With the lock
each waits alone, and the second finds the first's Thread; without it they
meet, and the second's insert breaks on the pair's unique key.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep, Seeking
from app.modules.matches.models import Match
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Profile
from app.modules.threads import repository, service
from app.modules.threads.models import Thread
from app.modules.threads.schemas import OpenThreadRequest
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.committed import fresh_man

COMPANY_WAIT_S = 1.0
RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def matched(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """Two fresh men, onboarded, seeking men, matched: (opener with 10 Velas,
    the other, the match). Everything the opens wrote is taken back after."""
    opener = await fresh_man(test_engine, credits=10)
    other = await fresh_man(test_engine)
    men = (opener, other)
    low, high = sorted(men)
    async with AsyncSession(test_engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id.in_(men))
            .values(onboarding_step=OnboardingStep.DONE)
        )
        await session.execute(
            update(Profile).where(Profile.user_id.in_(men)).values(seeking=Seeking.MEN)
        )
        match = Match(user_low=low, user_high=high)
        session.add(match)
        await session.flush()
        match_id = match.id
    try:
        yield opener, other, match_id
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(Notification).where(Notification.user_id.in_(men))
            )
            await session.execute(delete(Match).where(Match.id == match_id))
            await session.execute(
                delete(Thread).where(Thread.user_low == low, Thread.user_high == high)
            )
            await session.execute(
                update(Profile).where(Profile.user_id.in_(men)).values(seeking=None)
            )
            await session.execute(
                update(User)
                .where(User.id.in_(men))
                .values(onboarding_step=OnboardingStep.DOB)
            )


class Race:
    """Opens at once, each in a session of its own, and what the lock decided."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opened = 0
        self.open_at_lock: list[int] = []
        self.holding: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real_lock = repository.lock_pair

        async def lock_then_wait_for_company(
            session: AsyncSession, a: uuid.UUID, b: uuid.UUID
        ) -> None:
            self.open_at_lock.append(self.opened)
            await real_lock(session, a, b)
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

        monkeypatch.setattr(repository, "lock_pair", lock_then_wait_for_company)

    async def open(
        self, engine: AsyncEngine, redis: Redis, opener: uuid.UUID, match_id: uuid.UUID
    ) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, opener)
                assert user is not None
            self.opened += 1
            # Both open before either goes on: the overlap, forced.
            while self.opened < 2:
                await asyncio.sleep(0.01)
            return await service.open_thread(
                session,
                redis,
                user,
                OpenThreadRequest(match_id=match_id, shown_price=5),
            )


async def test_a_double_tap_opens_one_thread_and_charges_once(
    test_engine: AsyncEngine,
    test_redis: Redis,
    matched: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener, other, match_id = matched
    race = Race(monkeypatch)
    tasks = [
        asyncio.ensure_future(race.open(test_engine, test_redis, opener, match_id))
        for _ in range(2)
    ]
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert race.open_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    opened = [r for r in results if not isinstance(r, BaseException)]
    assert len(opened) == 2, results
    assert opened[0].id == opened[1].id
    low, high = sorted((opener, other))
    async with AsyncSession(test_engine) as session:
        threads = list(
            await session.scalars(
                select(Thread.id).where(
                    Thread.user_low == low, Thread.user_high == high
                )
            )
        )
        charges = list(
            await session.scalars(
                select(LedgerEntry.reason).where(
                    LedgerEntry.user_id == opener,
                    or_(LedgerEntry.ref_id.in_(threads), LedgerEntry.ref_id.is_(None)),
                    LedgerEntry.reason != "admin_grant",
                )
            )
        )
        balance = await session.scalar(
            select(Wallet.balance).where(Wallet.user_id == opener)
        )
    assert threads == [opened[0].id]
    assert [str(reason) for reason in charges] == ["thread_open"]
    assert balance == 5
