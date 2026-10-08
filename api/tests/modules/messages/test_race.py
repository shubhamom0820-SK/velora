"""Two sends at once in one Thread are one after the other (T-7.3): each holds
the Thread's row, so the count both read is never the same and none is lost,
and masking counts each message once.

Rows are committed for real, on two fresh men who both seek men and share a
committed Thread opened by the sender (his messages are free). The messages
and the Thread are taken back at the end, and the men put back as `fresh_man`
left them; nothing here writes a ledger row (06-TESTING, "Tests that commit
rows").

The race is forced (concurrency-tests-must-prove-overlap): both sends are
inside open transactions before either asks for the Thread's row, and each,
holding it, waits for the other to hold it too. With the lock each waits
alone; without it they meet, both read a count of 0, and both write 1.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock
from app.core.enums import (
    LedgerReason,
    MessageKind,
    OnboardingStep,
    Seeking,
    ThreadOrigin,
)
from app.core.providers.storage import FakeStorage
from app.modules.messages import repository, service
from app.modules.messages.models import Message, MessageUnlock
from app.modules.messages.schemas import SendMessageRequest
from app.modules.profiles.models import Profile
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.committed import fresh_man
from tests.conftest import make_test_settings

COMPANY_WAIT_S = 1.0
RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def thread(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """(the sender, the Thread he opened with another fresh man). Everything
    the sends wrote is taken back after."""
    sender = await fresh_man(test_engine)
    other = await fresh_man(test_engine)
    men = (sender, other)
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
        row = Thread(
            user_low=low,
            user_high=high,
            origin=ThreadOrigin.MATCH,
            opened_by=sender,
            expires_at=clock.now() + timedelta(hours=24),
        )
        session.add(row)
        await session.flush()
        thread_id = row.id
    try:
        yield sender, thread_id
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(delete(Message).where(Message.thread_id == thread_id))
            await session.execute(delete(Thread).where(Thread.id == thread_id))
            await session.execute(
                update(Profile).where(Profile.user_id.in_(men)).values(seeking=None)
            )
            await session.execute(
                update(User)
                .where(User.id.in_(men))
                .values(onboarding_step=OnboardingStep.DOB)
            )


class Race:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opened = 0
        self.open_at_lock: list[int] = []
        self.holding: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real = repository.thread_of

        async def lock_then_wait_for_company(
            session: AsyncSession, thread_id: uuid.UUID, viewer_id: uuid.UUID, **kw: Any
        ) -> Thread | None:
            if not kw.get("lock"):
                return await real(session, thread_id, viewer_id, **kw)
            self.open_at_lock.append(self.opened)
            found = await real(session, thread_id, viewer_id, **kw)
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
            return found

        monkeypatch.setattr(repository, "thread_of", lock_then_wait_for_company)

    async def send(
        self, engine: AsyncEngine, redis: Redis, sender: uuid.UUID, thread_id: uuid.UUID
    ) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, sender)
                assert user is not None
            self.opened += 1
            while self.opened < 2:
                await asyncio.sleep(0.01)
            return await service.send(
                session,
                redis,
                user,
                thread_id,
                SendMessageRequest(
                    client_msg_id=uuid.uuid4(), kind=MessageKind.TEXT, body="Hello"
                ),
                storage=FakeStorage(),
                settings=make_test_settings(),
            )


async def test_two_sends_at_once_are_both_counted(
    test_engine: AsyncEngine,
    test_redis: Redis,
    thread: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender, thread_id = thread
    race = Race(monkeypatch)
    tasks = [
        asyncio.ensure_future(race.send(test_engine, test_redis, sender, thread_id))
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
    assert not [r for r in results if isinstance(r, BaseException)], results
    async with AsyncSession(test_engine) as session:
        count = await session.scalar(
            select(Thread.message_count).where(Thread.id == thread_id)
        )
    assert count == 2


# --- Two unlocks at once (T-7.9) ------------------------------------------------
#
# A double tap on a locked voice note records one unlock and charges once. Rows
# are committed for real: a fresh man with 10 Velas unlocks a voice note from
# another fresh man, in a committed Thread between them. The unlock, the note
# and the Thread are taken back at the end; the one `voice_unlock` ledger row
# stays, as every fresh man's rows do (06-TESTING, "Tests that commit rows").
#
# Forced (concurrency-tests-must-prove-overlap): both unlocks are inside open
# transactions before either records the unlock, and each, once its insert
# returns, waits for the other's to return too. The primary key makes the
# second insert wait until the first commits, so each waits alone and the
# second finds the unlock there: one row, one charge. Recorded any other way
# (the row read first, then written), they meet, and both charge.


@pytest.fixture
async def voice_note(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """(the man who unlocks, with 10 Velas; the voice note he unlocks)."""
    listener = await fresh_man(test_engine, credits=10)
    sender = await fresh_man(test_engine)
    men = (listener, sender)
    low, high = sorted(men)
    async with AsyncSession(test_engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id.in_(men))
            .values(onboarding_step=OnboardingStep.DONE)
        )
        row = Thread(
            user_low=low,
            user_high=high,
            origin=ThreadOrigin.MATCH,
            opened_by=sender,
            expires_at=clock.now() + timedelta(hours=24),
        )
        session.add(row)
        await session.flush()
        thread_id = row.id
        note = Message(
            thread_id=thread_id,
            sender_id=sender,
            kind=MessageKind.VOICE,
            media_key=f"voice/{thread_id}/{uuid.uuid4()}.webm",
            duration_s=12,
            client_msg_id=uuid.uuid4(),
        )
        session.add(note)
        await session.flush()
        note_id = note.id
    try:
        yield listener, note_id
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(MessageUnlock).where(MessageUnlock.message_id == note_id)
            )
            await session.execute(delete(Message).where(Message.thread_id == thread_id))
            await session.execute(delete(Thread).where(Thread.id == thread_id))
            await session.execute(
                update(User)
                .where(User.id.in_(men))
                .values(onboarding_step=OnboardingStep.DOB)
            )


class UnlockRace:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opened = 0
        self.open_at_insert: list[int] = []
        self.returned: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real = repository.add_unlock

        async def insert_then_wait_for_company(
            session: AsyncSession, user_id: uuid.UUID, message_id: uuid.UUID
        ) -> bool:
            self.open_at_insert.append(self.opened)
            added = await real(session, user_id, message_id)
            me = id(session)
            self.returned.add(me)
            if len(self.returned) > 1:
                self.company.set()
            try:
                await asyncio.wait_for(self.company.wait(), timeout=COMPANY_WAIT_S)
            except TimeoutError:
                self.waited_alone.append(True)
            else:
                self.waited_alone.append(False)
            self.returned.discard(me)
            return added

        monkeypatch.setattr(repository, "add_unlock", insert_then_wait_for_company)

    async def unlock(
        self, engine: AsyncEngine, listener: uuid.UUID, note_id: uuid.UUID
    ) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, listener)
                assert user is not None
            self.opened += 1
            while self.opened < 2:
                await asyncio.sleep(0.01)
            return await service.unlock(
                session,
                user,
                note_id,
                shown=5,
                storage=FakeStorage(),
                settings=make_test_settings(),
            )


async def test_two_unlocks_at_once_record_one_and_charge_once(
    test_engine: AsyncEngine,
    voice_note: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener, note_id = voice_note
    race = UnlockRace(monkeypatch)
    tasks = [
        asyncio.ensure_future(race.unlock(test_engine, listener, note_id))
        for _ in range(2)
    ]
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert race.open_at_insert == [2, 2]
    assert race.waited_alone == [True, True]
    assert not [r for r in results if isinstance(r, BaseException)], results
    async with AsyncSession(test_engine) as session:
        unlocks = await session.scalar(
            select(func.count())
            .select_from(MessageUnlock)
            .where(MessageUnlock.message_id == note_id)
        )
        charges = (
            await session.scalars(
                select(LedgerEntry.delta).where(
                    LedgerEntry.user_id == listener,
                    LedgerEntry.reason == LedgerReason.VOICE_UNLOCK,
                )
            )
        ).all()
    assert unlocks == 1
    assert list(charges) == [-5]
