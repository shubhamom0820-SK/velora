"""Two requests at once from one person to another are one after the other
(T-8.4): the second finds the first, and nothing breaks on the live pair's
unique index.

Rows are committed for real, so the two requests run on two connections. The
requester is a woman: hers costs nothing, so nothing here writes a ledger row
(06-TESTING, "Tests that commit rows"). The owner is a fresh man with two
approved private photos. The requests and photos are taken back at the end,
and both put back as never onboarded; the users stay, as every fresh man does.

The race is forced, never trusted to `gather`
(concurrency-tests-must-prove-overlap): both are inside open transactions
before either asks for the requester's lock, and each, holding it, waits for
the other to hold it too. With the lock each waits alone; without it they meet,
both find no request, and the second insert breaks the unique index.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import (
    Gender,
    OnboardingStep,
    PhotoKind,
    ReviewStatus,
    Seeking,
)
from app.modules.album import repository, service
from app.modules.album.models import AlbumRequest
from app.modules.album.schemas import CreateAlbumRequest
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.committed import fresh_man, lock_numbers, next_fresh_number
from tests.conftest import make_test_settings

COMPANY_WAIT_S = 1.0
RACE_TIMEOUT_S = 10.0


async def _committed_woman(engine: AsyncEngine) -> uuid.UUID:
    settings = make_test_settings()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            await lock_numbers(session)
            phone = await next_fresh_number(session, settings)
            account = await users_service.create_account(session, phone, settings)
            account.user.gender = Gender.FEMALE
            account.user.dob = date(2000, 1, 1)
            account.user.is_verified = True
            account.user.onboarding_step = OnboardingStep.DONE
            account.profile.first_name = "Race"
            account.profile.seeking = Seeking.MEN
        return account.user.id


@pytest.fixture
async def pair(test_engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """(a woman asking, a man whose album she asks for)."""
    man = await fresh_man(test_engine)
    woman = await _committed_woman(test_engine)
    async with AsyncSession(test_engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.DONE)
        )
        await session.execute(
            update(Profile).where(Profile.user_id == man).values(seeking=Seeking.WOMEN)
        )
        for _ in range(2):
            photo_id = uuid.uuid4()
            session.add(
                Photo(
                    id=photo_id,
                    user_id=man,
                    kind=PhotoKind.PRIVATE,
                    raw_key=f"raw/{man}/{photo_id}",
                    scored_key=f"scored/{man}/{photo_id}.jpg",
                    status=ReviewStatus.APPROVED,
                )
            )
    try:
        yield woman, man
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(AlbumRequest).where(AlbumRequest.requester_id == woman)
            )
            await session.execute(delete(Photo).where(Photo.user_id == man))
            await session.execute(
                update(Profile)
                .where(Profile.user_id.in_((man, woman)))
                .values(seeking=None)
            )
            await session.execute(
                update(User)
                .where(User.id.in_((man, woman)))
                .values(onboarding_step=OnboardingStep.DOB)
            )


class Race:
    """Requests at once, each in a session of its own."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.started = 0
        self.started_at_lock: list[int] = []
        self.holding: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real_lock = repository.lock_requester

        async def lock_then_wait_for_company(
            session: AsyncSession, requester_id: uuid.UUID
        ) -> None:
            self.started_at_lock.append(self.started)
            await real_lock(session, requester_id)
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

        monkeypatch.setattr(repository, "lock_requester", lock_then_wait_for_company)

    async def ask(
        self, engine: AsyncEngine, requester: uuid.UUID, owner: uuid.UUID
    ) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, requester)
                assert user is not None
            self.started += 1
            # Both start before either goes on: the overlap, forced.
            while self.started < 2:
                await asyncio.sleep(0.01)
            return await service.ask(
                session,
                user,
                CreateAlbumRequest(owner_id=owner, shown_price=0),
                settings=make_test_settings(),
            )

    async def run(self, *asks: Any) -> list[Any]:
        tasks = [asyncio.ensure_future(a) for a in asks]
        try:
            async with asyncio.timeout(RACE_TIMEOUT_S):
                return await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def test_two_requests_at_once_are_one_request(
    test_engine: AsyncEngine,
    pair: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    woman, man = pair
    race = Race(monkeypatch)

    results = await race.run(*(race.ask(test_engine, woman, man) for _ in range(2)))

    assert race.started_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    assert not any(isinstance(r, BaseException) for r in results), results
    assert results[0].id == results[1].id
    async with AsyncSession(test_engine) as session:
        rows = list(
            await session.scalars(
                select(AlbumRequest.id).where(AlbumRequest.requester_id == woman)
            )
        )
    assert rows == [results[0].id]
