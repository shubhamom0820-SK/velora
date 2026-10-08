"""The hour under contention (T-7.6, D-560): every move of `expires_at` holds
the Thread's row, and the minute's sweep skips a row someone holds rather
than waiting on it or overriding it.

Rows are committed for real, on two fresh men and a Thread between them,
taken back at the end with its messages (06-TESTING, "Tests that commit
rows"). No ledger row is committed: the Extend race stubs the charge, since
the race it proves is the hour's, and a committed `thread_extend` row would
outlive the run and refuse T-5.2's downgrade (D-251). The sends are hers:
played by one of the men under a woman's gender, as the service reads it,
since a gender can't change once set (T-1.9) and a committed woman would
outlive the run.

Each race is forced (concurrency-tests-must-prove-overlap) and gathered under
a timeout, so a broken guard fails rather than hangs.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import build_sessionmaker
from app.core.enums import Gender, MessageKind, ThreadOrigin, ThreadStatus
from app.core.providers.storage import FakeStorage
from app.modules.messages import repository as messages_repository
from app.modules.messages import service as messages_service
from app.modules.messages.models import Message
from app.modules.messages.schemas import SendMessageRequest
from app.modules.pricing import service as pricing_service
from app.modules.threads import repository as threads_repository
from app.modules.threads import service as threads_service
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.workers.tasks import thread_clock
from tests.committed import fresh_man
from tests.conftest import make_test_settings

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST
COMPANY_WAIT_S = 1.0
HOLD_S = 5.0
RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def pair(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """(one, the other, their Thread, opened by the other and due at 13:00).
    The Thread and its messages are taken back after."""
    one = await fresh_man(test_engine)
    other = await fresh_man(test_engine)
    low, high = sorted((one, other))
    async with AsyncSession(test_engine) as session, session.begin():
        row = Thread(
            user_low=low,
            user_high=high,
            origin=ThreadOrigin.MATCH,
            opened_by=other,
            expires_at=NOON + timedelta(hours=1),
        )
        session.add(row)
        await session.flush()
        thread_id = row.id
    try:
        yield one, other, thread_id
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(delete(Message).where(Message.thread_id == thread_id))
            await session.execute(delete(Thread).where(Thread.id == thread_id))


async def _thread(engine: AsyncEngine, thread_id: uuid.UUID) -> Thread:
    async with AsyncSession(engine) as session:
        found = await session.get(Thread, thread_id)
    assert found is not None
    return found


async def _gather(*tasks: asyncio.Future[Any]) -> list[Any]:
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            return await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# --- Two Extends at once --------------------------------------------------------------


async def test_two_extends_at_once_each_add_their_day(
    test_engine: AsyncEngine,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two taps with two keys, two Extends paid: both inside open transactions
    before either asks for the Thread, each, holding it, waiting for the other
    to hold it too. With the lock each waits alone and the second adds to the
    first's day; without it they meet, both read 13:00, and one day is lost."""
    from app.core import clock

    clock.freeze(NOON)
    try:
        buyer, _, thread_id = pair
        opened = 0
        open_at_lock: list[int] = []
        holding: set[int] = set()
        company = asyncio.Event()
        waited_alone: list[bool] = []
        real = threads_repository.my_thread

        async def lock_then_wait_for_company(
            session: AsyncSession, thread_id: uuid.UUID, viewer_id: uuid.UUID, **kw: Any
        ) -> Thread | None:
            open_at_lock.append(opened)
            found = await real(session, thread_id, viewer_id, **kw)
            me = id(session)
            holding.add(me)
            if len(holding) > 1:
                company.set()
            try:
                await asyncio.wait_for(company.wait(), timeout=COMPANY_WAIT_S)
            except TimeoutError:
                waited_alone.append(True)
            else:
                waited_alone.append(False)
            holding.discard(me)
            return found

        async def charged(*_: Any, **__: Any) -> None:
            return None

        monkeypatch.setattr(threads_repository, "my_thread", lock_then_wait_for_company)
        monkeypatch.setattr(pricing_service, "charge", charged)

        async def extend(key: str) -> Any:
            nonlocal opened
            async with AsyncSession(test_engine, expire_on_commit=False) as session:
                async with session.begin():
                    user = await session.get(User, buyer)
                    assert user is not None
                opened += 1
                while opened < 2:
                    await asyncio.sleep(0.01)
                return await threads_service.extend(
                    session, user, thread_id, key=key, shown_price=10
                )

        results = await _gather(
            asyncio.ensure_future(extend("tap-0001")),
            asyncio.ensure_future(extend("tap-0002")),
        )
    finally:
        clock.unfreeze()

    assert open_at_lock == [2, 2]
    assert waited_alone == [True, True]
    assert not [r for r in results if isinstance(r, BaseException)], results
    after = await _thread(test_engine, thread_id)
    assert after.expires_at == NOON + timedelta(hours=49)


# --- Her message and the sweep --------------------------------------------------------


def _her(user_id: uuid.UUID) -> User:
    """Her, as the send reads her: an id and a gender."""
    return User(id=user_id, gender=Gender.FEMALE)


async def _her_send(
    engine: AsyncEngine, redis: Redis, user_id: uuid.UUID, thread_id: uuid.UUID
) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await messages_service.send(
            session,
            redis,
            _her(user_id),
            thread_id,
            SendMessageRequest(
                client_msg_id=uuid.uuid4(), kind=MessageKind.TEXT, body="Hello"
            ),
            storage=FakeStorage(),
            settings=make_test_settings(),
        )


async def test_the_sweep_skips_a_thread_her_send_holds(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Her send holds the Thread, past its hour by the clock, when the sweep
    runs: the sweep skips it without waiting (`SKIP LOCKED`); her message is
    delivered and moves nothing; the next sweep expires it. Without the skip
    the sweep waits on her, and its own timeout fails the test."""
    from app.core import clock

    she, _, thread_id = pair
    holding = asyncio.Event()
    swept = asyncio.Event()
    waited_for_sweep: list[bool] = []
    real = messages_repository.thread_of

    async def hold_until_swept(
        session: AsyncSession, thread_id: uuid.UUID, viewer_id: uuid.UUID, **kw: Any
    ) -> Thread | None:
        found = await real(session, thread_id, viewer_id, **kw)
        if kw.get("lock"):
            holding.set()
            try:
                await asyncio.wait_for(swept.wait(), timeout=HOLD_S)
            except TimeoutError:
                waited_for_sweep.append(False)
            else:
                waited_for_sweep.append(True)
        return found

    monkeypatch.setattr(messages_repository, "thread_of", hold_until_swept)
    sessions = build_sessionmaker(test_engine)
    clock.freeze(NOON + timedelta(hours=1, seconds=30))
    try:

        async def sweep_while_she_holds() -> int:
            await asyncio.wait_for(holding.wait(), timeout=HOLD_S)
            async with asyncio.timeout(COMPANY_WAIT_S * 2):
                taken = await thread_clock.expire_threads(sessions, test_redis)
            swept.set()
            return taken

        sent, during = await _gather(
            asyncio.ensure_future(_her_send(test_engine, test_redis, she, thread_id)),
            asyncio.ensure_future(sweep_while_she_holds()),
        )
        after_her = await _thread(test_engine, thread_id)
        later = await thread_clock.expire_threads(sessions, test_redis)
    finally:
        clock.unfreeze()

    assert not isinstance(during, BaseException), during
    assert not isinstance(sent, BaseException), sent
    assert waited_for_sweep == [True]
    assert during == 0
    assert (after_her.status, after_her.expires_at) == (
        ThreadStatus.ACTIVE,
        NOON + timedelta(hours=1),
    )
    assert later == 1
    final = await _thread(test_engine, thread_id)
    assert (final.status, final.expires_at) == (
        ThreadStatus.EXPIRED,
        NOON + timedelta(hours=1),
    )


async def test_her_send_waits_for_the_sweep_and_revives_nothing(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other order: the sweep holds the Thread, expiring it, and her send
    is seen waiting on its lock (`pg_locks`) before the sweep commits. Then
    her message is delivered into the expired Thread and moves nothing."""
    from app.core import clock

    she, _, thread_id = pair
    real = threads_repository.expire_due
    saw_her_wait: list[bool] = []

    async def expire_then_wait_for_her(*args: Any, **kw: Any) -> Any:
        rows = await real(*args, **kw)
        if rows:
            her = asyncio.ensure_future(
                _her_send(test_engine, test_redis, she, thread_id)
            )
            waiting.append(her)
            saw_her_wait.append(await _someone_waits_on_a_lock(test_engine))
        return rows

    waiting: list[asyncio.Future[Any]] = []
    monkeypatch.setattr(threads_repository, "expire_due", expire_then_wait_for_her)
    clock.freeze(NOON + timedelta(hours=1, seconds=30))
    try:
        taken = await asyncio.wait_for(
            thread_clock.expire_threads(build_sessionmaker(test_engine), test_redis),
            timeout=RACE_TIMEOUT_S,
        )
        [sent] = await _gather(*waiting)
    finally:
        clock.unfreeze()

    assert taken == 1
    assert saw_her_wait == [True]
    assert not isinstance(sent, BaseException), sent
    final = await _thread(test_engine, thread_id)
    assert (final.status, final.expires_at) == (
        ThreadStatus.EXPIRED,
        NOON + timedelta(hours=1),
    )
    async with AsyncSession(test_engine) as session:
        delivered = await session.scalars(
            select(Message.id).where(Message.thread_id == thread_id)
        )
        assert len(delivered.all()) == 1


async def _someone_waits_on_a_lock(engine: AsyncEngine) -> bool:
    """Whether a session on this database is waiting for a lock, within a
    few seconds: her send, blocked on the Thread the sweep holds."""
    for _ in range(int(HOLD_S / 0.05)):
        async with AsyncSession(engine) as session:
            waiting = await session.scalar(
                text(
                    "select count(*) from pg_stat_activity "
                    "where wait_event_type = 'Lock' and datname = current_database()"
                )
            )
        if waiting:
            return True
        await asyncio.sleep(0.05)
    return False
