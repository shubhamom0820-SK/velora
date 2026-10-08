"""The knot under contention (T-7.7): a tap holds the Thread's row, so two
taps at once are one after the other and the second makes the Knot; and the
minute's sweep, in either order with a tap, never expires a Knot.

Rows are committed for real, on two fresh men and a Thread between them (two
men tie as anyone does), taken back at the end with the notifications the taps
wrote (06-TESTING, "Tests that commit rows"). Nothing here is charged: a knot
is free (D-003). Each race is forced (concurrency-tests-must-prove-overlap)
and gathered under a timeout, so a broken guard fails rather than hangs.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import events
from app.core.db import build_sessionmaker
from app.core.enums import ThreadOrigin, ThreadStatus
from app.modules.notifications.models import Notification
from app.modules.threads import repository as threads_repository
from app.modules.threads import service as threads_service
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.workers.tasks import thread_clock
from tests.committed import fresh_man

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST
COMPANY_WAIT_S = 1.0
HOLD_S = 5.0
RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def pair(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """(one, the other, their Thread, due at 13:00). The Thread and both men's
    notifications are taken back after."""
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
            await session.execute(
                delete(Notification).where(Notification.user_id.in_([one, other]))
            )
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


async def _tie(
    engine: AsyncEngine, user_id: uuid.UUID, thread_id: uuid.UUID
) -> list[events.Event]:
    """One tap, in a session of its own; the events it committed."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            user = await session.get(User, user_id)
            assert user is not None
        await threads_service.tie(session, user, thread_id)
        return events.take_committed(session)


async def _tap(engine: AsyncEngine, thread_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """`user_id`'s tap already there, written directly."""
    thread = await _thread(engine, thread_id)
    column = "low_knot_at" if user_id == thread.user_low else "high_knot_at"
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            text(f"UPDATE threads SET {column} = :at WHERE id = :id"),
            {"at": NOON, "id": thread_id},
        )


# --- Two taps at once ------------------------------------------------------------------


async def test_two_taps_at_once_make_one_knot(
    test_engine: AsyncEngine,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both taps inside open transactions before either asks for the Thread;
    each, holding it, waits for the other to hold it too. With the lock each
    waits alone, the second finds the first's tap, and they are a Knot, told
    once each. Without it they meet, each reads no tap but its own, and two
    taps make no Knot."""
    from app.core import clock

    clock.freeze(NOON)
    try:
        one, other, thread_id = pair
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

        monkeypatch.setattr(threads_repository, "my_thread", lock_then_wait_for_company)

        async def tap(user_id: uuid.UUID) -> list[events.Event]:
            nonlocal opened
            async with AsyncSession(test_engine, expire_on_commit=False) as session:
                async with session.begin():
                    user = await session.get(User, user_id)
                    assert user is not None
                opened += 1
                while opened < 2:
                    await asyncio.sleep(0.01)
                await threads_service.tie(session, user, thread_id)
                return events.take_committed(session)

        results = await _gather(
            asyncio.ensure_future(tap(one)), asyncio.ensure_future(tap(other))
        )
    finally:
        clock.unfreeze()

    assert open_at_lock == [2, 2]
    assert waited_alone == [True, True]
    assert not [r for r in results if isinstance(r, BaseException)], results
    after = await _thread(test_engine, thread_id)
    assert after.status is ThreadStatus.KNOTTED
    assert (after.knotted_at, after.expires_at) == (NOON, None)
    told = sorted((str(e.user_id), e.type) for batch in results for e in batch)
    first = next(batch for batch in results if len(batch) == 1)[0]
    asked = first.user_id
    assert told == sorted(
        [
            (str(asked), "knot.requested"),
            (str(one), "knot.accepted"),
            (str(other), "knot.accepted"),
        ]
    )


# --- A tap and the sweep ---------------------------------------------------------------


async def test_the_sweep_skips_a_thread_a_tap_holds_and_never_expires_the_knot(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other has tapped; the Thread is past its hour by the clock when the
    last tap holds it and the sweep runs. The sweep skips it without waiting
    (`SKIP LOCKED`), the tap makes the Knot, and the next sweep finds nothing:
    a Knot is never expired."""
    from app.core import clock

    one, other, thread_id = pair
    await _tap(test_engine, thread_id, other)
    holding = asyncio.Event()
    swept = asyncio.Event()
    waited_for_sweep: list[bool] = []
    real = threads_repository.my_thread

    async def hold_until_swept(
        session: AsyncSession, thread_id: uuid.UUID, viewer_id: uuid.UUID, **kw: Any
    ) -> Thread | None:
        found = await real(session, thread_id, viewer_id, **kw)
        holding.set()
        try:
            await asyncio.wait_for(swept.wait(), timeout=HOLD_S)
        except TimeoutError:
            waited_for_sweep.append(False)
        else:
            waited_for_sweep.append(True)
        return found

    monkeypatch.setattr(threads_repository, "my_thread", hold_until_swept)
    sessions = build_sessionmaker(test_engine)
    clock.freeze(NOON + timedelta(hours=1, seconds=30))
    try:

        async def sweep_while_held() -> int:
            await asyncio.wait_for(holding.wait(), timeout=HOLD_S)
            async with asyncio.timeout(COMPANY_WAIT_S * 2):
                taken = await thread_clock.expire_threads(sessions, test_redis)
            swept.set()
            return taken

        tied, during = await _gather(
            asyncio.ensure_future(_tie(test_engine, one, thread_id)),
            asyncio.ensure_future(sweep_while_held()),
        )
        later = await thread_clock.expire_threads(sessions, test_redis)
    finally:
        clock.unfreeze()

    assert not isinstance(during, BaseException), during
    assert not isinstance(tied, BaseException), tied
    assert waited_for_sweep == [True]
    assert during == 0
    assert later == 0
    final = await _thread(test_engine, thread_id)
    assert (final.status, final.expires_at) == (ThreadStatus.KNOTTED, None)


async def test_a_tap_waits_for_the_sweep_and_ties_the_expired_thread(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other order: the sweep holds the Thread, expiring it, and the last
    tap is seen waiting on its lock (`pg_stat_activity`) before the sweep
    commits. Then the tap reads the expired Thread and ties it straight into a
    Knot (T-7.7)."""
    from app.core import clock

    one, other, thread_id = pair
    await _tap(test_engine, thread_id, other)
    real = threads_repository.expire_due
    saw_the_tap_wait: list[bool] = []
    waiting: list[asyncio.Future[Any]] = []

    async def expire_then_wait_for_the_tap(*args: Any, **kw: Any) -> Any:
        rows = await real(*args, **kw)
        if rows:
            waiting.append(asyncio.ensure_future(_tie(test_engine, one, thread_id)))
            saw_the_tap_wait.append(await _someone_waits_on_a_lock(test_engine))
        return rows

    monkeypatch.setattr(threads_repository, "expire_due", expire_then_wait_for_the_tap)
    clock.freeze(NOON + timedelta(hours=1, seconds=30))
    try:
        taken = await asyncio.wait_for(
            thread_clock.expire_threads(build_sessionmaker(test_engine), test_redis),
            timeout=RACE_TIMEOUT_S,
        )
        [tied] = await _gather(*waiting)
    finally:
        clock.unfreeze()

    assert taken == 1
    assert saw_the_tap_wait == [True]
    assert not isinstance(tied, BaseException), tied
    final = await _thread(test_engine, thread_id)
    assert (final.status, final.expires_at) == (ThreadStatus.KNOTTED, None)


async def _someone_waits_on_a_lock(engine: AsyncEngine) -> bool:
    """Whether a session on this database is waiting for a lock, within a
    few seconds: the tap, blocked on the Thread the sweep holds."""
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
