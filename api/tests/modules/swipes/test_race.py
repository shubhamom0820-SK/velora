"""Two people liking each other at once make one match (T-6.4), and both hear
of it: `match.created` on each one's channel, published when the request ends.

Rows are committed for real, on two fresh men who both seek men (no woman is
needed for a mutual like, and a like writes no ledger row, which could never be
deleted). What they committed, swipes, the match and its notifications, is
taken back at the end, and they are put back as `fresh_man` left them
(06-TESTING, "Tests that commit rows").

The race is forced, never trusted to `gather` (concurrency-tests-must-prove-overlap):
both swipes are inside open transactions before either asks for the pair's
lock, and each, holding it, waits for the other to hold it too. With the lock
nobody gets in beside the holder, so each waits alone; without it they meet,
and neither sees the other's uncommitted like.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock
from app.core.enums import OnboardingStep, Role, Seeking, SwipeDirection
from app.core.providers import FakeProviders
from app.core.security import make_access_token
from app.main import close_resources, create_app
from app.modules.matches.models import Match
from app.modules.notifications.models import Notification
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile
from app.modules.swipes import repository, service
from app.modules.swipes.models import Swipe
from app.modules.users.models import User
from tests.committed import fresh_man
from tests.conftest import make_test_settings
from tests.modules.discovery.support import HERE

COMPANY_WAIT_S = 1.0


@pytest.fixture
async def pair(test_engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """Two fresh men, onboarded, seeking men, at one grid point; every row
    their swipes made taken back afterwards, and they put back as they were."""
    men = (await fresh_man(test_engine), await fresh_man(test_engine))
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
    try:
        yield men
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(Notification).where(Notification.user_id.in_(men))
            )
            await session.execute(
                delete(Match).where(Match.user_low.in_(men) | Match.user_high.in_(men))
            )
            await session.execute(delete(Swipe).where(Swipe.swiper_id.in_(men)))
            await session.execute(
                update(Profile)
                .where(Profile.user_id.in_(men))
                .values(seeking=None, location=None)
            )
            await session.execute(
                update(User)
                .where(User.id.in_(men))
                .values(onboarding_step=OnboardingStep.DOB)
            )


class Race:
    """Swipes at once, each in a session of its own, and what the lock decided."""

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

    async def swipe(
        self, engine: AsyncEngine, redis: Redis, swiper: uuid.UUID, target: uuid.UUID
    ) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, swiper)
                assert user is not None
            self.opened += 1
            # Both open before either goes on: the overlap, forced.
            while self.opened < 2:
                await asyncio.sleep(0.01)
            return await service.swipe(
                session, redis, user, target, SwipeDirection.LIKE
            )


async def test_two_likes_at_once_make_one_match(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b = pair
    race = Race(monkeypatch)

    results = await asyncio.gather(
        race.swipe(test_engine, test_redis, a, b),
        race.swipe(test_engine, test_redis, b, a),
    )

    assert race.open_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    assert sorted(r.matched for r in results) == [False, True]
    async with AsyncSession(test_engine) as session:
        matches = await session.scalar(
            select(func.count())
            .select_from(Match)
            .where(Match.user_low.in_(pair), Match.user_high.in_(pair))
        )
        swipes = await session.scalar(
            select(func.count()).select_from(Swipe).where(Swipe.swiper_id.in_(pair))
        )
    assert (matches, swipes) == (1, 2)
    made = next(r for r in results if r.matched)
    assert made.match_id is not None


# --- Both told: match.created, published when the request ends ----------------------


@pytest.fixture
async def real_app(test_redis: Redis) -> AsyncIterator[FastAPI]:
    """The app with its own `get_session`, which publishes (P-64)."""
    application = create_app(make_test_settings())
    application.state.providers = FakeProviders().as_providers()
    try:
        yield application
    finally:
        await close_resources(application)


async def test_a_match_is_published_to_both(
    real_app: FastAPI, test_redis: Redis, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = pair
    settings = make_test_settings()
    pubsub = test_redis.pubsub()
    await pubsub.subscribe(f"user:{a}", f"user:{b}")
    for _ in range(2):
        confirmed = await pubsub.get_message(timeout=2.0)
        assert confirmed is not None and confirmed["type"] == "subscribe"
    transport = ASGITransport(app=real_app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for swiper, target in ((a, b), (b, a)):
                token = make_access_token(
                    swiper, Role.USER, settings, auth_time=clock.now()
                )
                response = await client.post(
                    "/v1/swipes",
                    json={"target_id": str(target), "dir": "like"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 200, response.text
        match_id = response.json()["match_id"]
        heard: dict[str, dict[str, Any]] = {}
        for _ in range(2):
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=2.0
            )
            assert message is not None
            heard[message["channel"].decode()] = json.loads(message["data"])
        assert (
            await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            is None
        )
    finally:
        await pubsub.aclose()  # type: ignore[no-untyped-call]

    assert set(heard) == {f"user:{a}", f"user:{b}"}
    for one, other in ((a, b), (b, a)):
        envelope = heard[f"user:{one}"]
        assert (envelope["type"], envelope["data"]) == (
            "match.created",
            {"match_id": match_id, "user_id": str(other)},
        )
