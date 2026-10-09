"""`send_push` in the worker (T-9.4, D-850): a wake on `wake:send_push` sends
what waits at once, and the worker's minute sends what a lost wake left.
Never an ARQ job. Committed rows, the man kept, his push rows taken back."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import events
from app.core.providers import FakeProviders
from app.core.redis import build_redis
from app.modules.notifications.models import PushOutbox, PushSubscription
from app.workers import main as worker
from tests.committed import fresh_man
from tests.conftest import make_test_settings
from tests.infra import TEST_REDIS_URL
from tests.modules.notifications.support import browser_keys


@pytest.fixture
async def waiting(test_engine: AsyncEngine) -> AsyncIterator[uuid.UUID]:
    man = await fresh_man(test_engine)
    _, keys = browser_keys()
    async with AsyncSession(test_engine) as session, session.begin():
        session.add(
            PushSubscription(
                user_id=man,
                endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
                p256dh=keys["p256dh"],
                auth=keys["auth"],
            )
        )
        session.add(PushOutbox(user_id=man, kind="match", payload={"match_id": "m"}))
    try:
        yield man
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(delete(PushOutbox).where(PushOutbox.user_id == man))
            await session.execute(
                delete(PushSubscription).where(PushSubscription.user_id == man)
            )


async def _worker(fake: FakeProviders) -> dict[str, Any]:
    ctx: dict[str, Any] = {"redis": build_redis(TEST_REDIS_URL)}
    await worker.open_resources(ctx, make_test_settings(), fake.as_providers())
    return ctx


async def test_a_wake_sends_the_waiting_push_at_once(
    test_redis: Redis, waiting: uuid.UUID
) -> None:
    fake = FakeProviders()
    ctx = await _worker(fake)
    listener = worker.listen_for_pushes(ctx, make_test_settings())
    listening = asyncio.create_task(listener.run())
    try:
        async with asyncio.timeout(5):
            await listener.subscribed.wait()
        await events.publish([events.Event(waiting, events.PUSH_WAKE, {})], test_redis)
        async with asyncio.timeout(5):
            while not fake.push.sent:
                await asyncio.sleep(0.05)
    finally:
        listening.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listening
        await worker.shutdown(ctx)
        await ctx["redis"].aclose()

    [(_, data)] = fake.push.sent
    assert data == {"kind": "match"}


async def test_the_minute_sends_what_a_lost_wake_left(
    test_redis: Redis, waiting: uuid.UUID
) -> None:
    fake = FakeProviders()
    ctx = await _worker(fake)
    try:
        done = await worker.each_minute(ctx)._work()
    finally:
        await worker.shutdown(ctx)
        await ctx["redis"].aclose()

    assert done["push_sent"] == 1
    assert len(fake.push.sent) == 1
