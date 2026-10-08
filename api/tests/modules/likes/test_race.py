"""Two reveals of one like at once pay once (T-6.7, D-542), and both answer
with the profile.

Rows are committed for real, on two fresh men who both seek men: one likes
the other, who reveals him twice at once. The ledger row the reveal writes can
never be deleted, so the men are never deleted either (`tests/committed.py`);
everything else they committed, the like, the reveal, the view, is taken back,
and they are put back as `fresh_man` left them.

The race is forced, never trusted to `gather` (concurrency-tests-must-prove-
overlap): both requests are inside their transactions, past finding the like,
before either writes the reveal's row; each, having written it or waited on
the other's, then waits for the other to be past the write too. With the row's
key deciding, the second waits in Postgres until the first commits, so each
waits alone; and only the one that wrote the row pays.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import LedgerReason, OnboardingStep, Seeking, SwipeDirection
from app.core.pagination import PageParams
from app.core.queue import FakeQueue
from app.modules.discovery.models import ProfileView
from app.modules.likes import repository, service
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile
from app.modules.swipes.models import LikedYouReveal, Swipe
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.committed import fresh_man
from tests.conftest import make_test_settings
from tests.modules.discovery.support import HERE

ARRIVE_WAIT_S = 10.0
COMPANY_WAIT_S = 1.0


@pytest.fixture
async def liked(test_engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """(viewer, liker): two fresh men, onboarded, seeking men, at one grid
    point, the liker's like of the viewer committed; the viewer with 5 Velas.
    Everything but the ledger taken back afterwards."""
    viewer = await fresh_man(test_engine, credits=5)
    liker = await fresh_man(test_engine)
    men = (viewer, liker)
    async with AsyncSession(test_engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id.in_(men))
            .values(onboarding_step=OnboardingStep.DONE)
        )
        await session.execute(
            update(Profile)
            .where(Profile.user_id.in_(men))
            .values(seeking=Seeking.MEN, location=profiles_repository.point(*HERE))
        )
        # A `Card` needs a name and a username; a fresh man has neither.
        for man in men:
            await session.execute(
                update(Profile)
                .where(Profile.user_id == man)
                .values(first_name="Racer", username=f"racer{man.hex[:12]}")
            )
        session.add(Swipe(swiper_id=liker, target_id=viewer, dir=SwipeDirection.LIKE))
    try:
        yield viewer, liker
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(LikedYouReveal).where(LikedYouReveal.viewer_id == viewer)
            )
            await session.execute(
                delete(ProfileView).where(ProfileView.viewer_id == viewer)
            )
            await session.execute(delete(Swipe).where(Swipe.swiper_id.in_(men)))
            await session.execute(
                update(Profile)
                .where(Profile.user_id.in_(men))
                .values(seeking=None, location=None, first_name=None, username=None)
            )
            await session.execute(
                update(User)
                .where(User.id.in_(men))
                .values(onboarding_step=OnboardingStep.DOB)
            )


class Race:
    """Reveals at once, each in a session of its own, and what the row's key
    decided."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, calls: int) -> None:
        self.calls = calls
        self.arrived = 0
        self.all_arrived = asyncio.Event()
        self.in_transaction: list[bool] = []
        self.past: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real_record = repository.record_reveal

        async def arrive_record_then_wait_for_company(
            session: AsyncSession, viewer_id: uuid.UUID, liker_id: uuid.UUID
        ) -> bool:
            self.arrived += 1
            if self.arrived == self.calls:
                self.all_arrived.set()
            await asyncio.wait_for(self.all_arrived.wait(), ARRIVE_WAIT_S)
            self.in_transaction.append(session.in_transaction())
            wrote = await real_record(session, viewer_id, liker_id)
            me = id(session)
            self.past.add(me)
            if len(self.past) > 1:
                self.company.set()
            try:
                await asyncio.wait_for(self.company.wait(), COMPANY_WAIT_S)
            except TimeoutError:
                self.waited_alone.append(True)
            else:
                self.waited_alone.append(False)
            self.past.discard(me)
            return wrote

        monkeypatch.setattr(
            repository, "record_reveal", arrive_record_then_wait_for_company
        )

    async def reveal(self, engine: AsyncEngine, viewer: uuid.UUID, handle: str) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, viewer)
                assert user is not None
            try:
                return await service.reveal(
                    session, user, handle, shown_price=1, settings=make_test_settings()
                )
            except Exception as error:  # noqa: BLE001 — the test reads it
                return error


async def _handle(engine: AsyncEngine, viewer: uuid.UUID) -> str:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            user = await session.get(User, viewer)
        assert user is not None
        page = await service.likes(
            session,
            user,
            params=PageParams(cursor=None, limit=20),
            settings=make_test_settings(),
            queue=FakeQueue(),
        )
    [item] = page.items
    return item.handle


@pytest.mark.critical
async def test_two_reveals_at_once_pay_once_and_both_see_him(
    test_engine: AsyncEngine,
    liked: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    viewer, liker = liked
    handle = await _handle(test_engine, viewer)
    race = Race(monkeypatch, calls=2)

    outcomes = await asyncio.gather(
        race.reveal(test_engine, viewer, handle),
        race.reveal(test_engine, viewer, handle),
    )

    assert race.in_transaction == [True, True]
    assert race.waited_alone == [True, True]
    for outcome in outcomes:
        assert not isinstance(outcome, Exception), outcome
        assert outcome.id == liker
    async with AsyncSession(test_engine) as session:
        debits = list(
            await session.scalars(
                select(LedgerEntry.delta).where(
                    LedgerEntry.user_id == viewer,
                    LedgerEntry.reason == LedgerReason.LIKED_YOU_REVEAL,
                )
            )
        )
    assert debits == [-1]
