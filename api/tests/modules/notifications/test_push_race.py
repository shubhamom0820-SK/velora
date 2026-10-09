"""Two senders at once (T-9.4, D-850): the wake's and the minute's, or two
workers. Each push is sent once. Committed rows on separate connections, the
overlap forced, never hoped for (06-TESTING):

1. One sender is mid-send, its row claimed and no lock held; the other finds
   the claim and takes nothing.
2. One sender is mid-claim, the row locked; the other skips it (`SKIP
   LOCKED`) rather than wait, then sends it once the first lets go.

The man is committed for real (`tests/committed.py`) and kept; his outbox and
subscription rows are deleted at the end."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db import build_sessionmaker
from app.core.providers.push import FakePush, PushOutcome, PushSubscription, Urgency
from app.modules.notifications import sender
from app.modules.notifications.models import PushOutbox
from app.modules.notifications.models import PushSubscription as SubscriptionRow
from tests.committed import fresh_man
from tests.modules.notifications.support import browser_keys


class _HeldPush(FakePush):
    """Sends once `release` is set; `entered` says a send has begun."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def send(
        self,
        subscription: PushSubscription,
        payload: Mapping[str, object],
        *,
        ttl_s: int,
        urgency: Urgency = "normal",
    ) -> PushOutcome:
        self.entered.set()
        await self.release.wait()
        return await super().send(subscription, payload, ttl_s=ttl_s, urgency=urgency)


class _NoRedis:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"a match's push reached Redis: {name}")


@pytest.fixture
async def waiting(test_engine: AsyncEngine) -> AsyncIterator[uuid.UUID]:
    """A man, subscribed, with one match push waiting, all committed; his
    rows taken back after."""
    man = await fresh_man(test_engine)
    _, keys = browser_keys()
    async with AsyncSession(test_engine) as session, session.begin():
        session.add(
            SubscriptionRow(
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
                delete(SubscriptionRow).where(SubscriptionRow.user_id == man)
            )


async def _left(sessions: async_sessionmaker[AsyncSession], man: uuid.UUID) -> int:
    async with sessions() as session:
        rows = await session.scalars(
            select(PushOutbox.id).where(PushOutbox.user_id == man)
        )
        return len(rows.all())


async def test_a_push_mid_send_is_never_taken_by_another_sender(
    test_engine: AsyncEngine, waiting: uuid.UUID
) -> None:
    sessions = build_sessionmaker(test_engine)
    push = _HeldPush()
    first = asyncio.create_task(sender.send_waiting(sessions, _NoRedis(), push))  # type: ignore[arg-type]
    await asyncio.wait_for(push.entered.wait(), 10)

    try:
        # Bounded: a second sender that took the row would wait on the first's
        # held send for ever, and that is the failure this test is for.
        second = await asyncio.wait_for(
            sender.send_waiting(sessions, _NoRedis(), push),  # type: ignore[arg-type]
            10,
        )
    finally:
        push.release.set()

    assert second == {}
    assert await first == {"sent": 1}
    assert len(push.sent) == 1
    assert await _left(sessions, waiting) == 0


async def test_a_row_being_claimed_is_skipped_not_waited_on(
    test_engine: AsyncEngine, waiting: uuid.UUID
) -> None:
    sessions = build_sessionmaker(test_engine)
    push = FakePush()
    async with AsyncSession(test_engine) as holder, holder.begin():
        held = await holder.scalar(
            select(PushOutbox.id).where(PushOutbox.user_id == waiting).with_for_update()
        )
        assert held is not None

        skipped = await asyncio.wait_for(
            sender.send_waiting(sessions, _NoRedis(), push),  # type: ignore[arg-type]
            10,
        )

        assert skipped == {}
        assert push.sent == []

    assert await sender.send_waiting(sessions, _NoRedis(), push) == {"sent": 1}  # type: ignore[arg-type]
    assert len(push.sent) == 1
