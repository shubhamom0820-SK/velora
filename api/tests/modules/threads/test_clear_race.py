"""A clearing and a message at once (T-7.8, D-610): what existed when the
clearing ran is hidden, and whatever is written after it shows, however the
two meet.

A message's `created_at` is its send's transaction start (the database's
`now()`), taken before the send waits for the Thread's row. So a clearing
stamped with its own time would hide a message whose send began before it
and was written after: the third case. The clearing holds the Thread's row
as a send does, and stamps the newest message it then sees.

Rows are committed for real, on two fresh men who both seek men and share a
committed Thread opened by the sender (his messages are free). Messages,
clearings and the Thread are taken back at the end, and the men put back as
`fresh_man` left them; nothing here writes a ledger row (06-TESTING, "Tests
that commit rows").

Each overlap is forced and proved (concurrency-tests-must-prove-overlap): the
side that waits is seen blocked on the other's lock by Postgres itself
(`pg_blocking_pids`) before the holder lets go.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock
from app.core.enums import MessageKind, OnboardingStep, Seeking, ThreadOrigin
from app.core.pagination import PageParams
from app.modules.messages import repository as messages_repository
from app.modules.messages import service as messages_service
from app.modules.messages.models import Message
from app.modules.messages.schemas import SendMessageRequest
from app.modules.profiles.models import Profile
from app.modules.threads import repository as threads_repository
from app.modules.threads import service as threads_service
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from tests.committed import fresh_man

RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def pair(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """(the sender, the one who clears, their Thread, opened by the sender).
    Everything written is taken back after."""
    sender = await fresh_man(test_engine)
    clearer = await fresh_man(test_engine)
    men = (sender, clearer)
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
        yield sender, clearer, thread_id
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                delete(ThreadClear).where(ThreadClear.thread_id == thread_id)
            )
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


async def _blocked(engine: AsyncEngine, pid: int) -> None:
    """Until Postgres says the backend `pid` waits on another's lock."""
    while True:
        async with engine.connect() as conn:
            waits = await conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}
            )
        if waits:
            return
        await asyncio.sleep(0.01)


async def _pid(session: AsyncSession) -> int:
    pid = await session.scalar(text("SELECT pg_backend_pid()"))
    assert isinstance(pid, int)
    return pid


async def _user(session: AsyncSession, user_id: uuid.UUID) -> User:
    async with session.begin():
        user = await session.get(User, user_id)
    assert user is not None
    return user


async def _send(
    engine: AsyncEngine, redis: Redis, sender_id: uuid.UUID, thread_id: uuid.UUID
) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = await _user(session, sender_id)
        return await messages_service.send(
            session,
            redis,
            user,
            thread_id,
            SendMessageRequest(
                client_msg_id=uuid.uuid4(), kind=MessageKind.TEXT, body="Hello"
            ),
        )


async def _clear(
    engine: AsyncEngine, clearer_id: uuid.UUID, thread_id: uuid.UUID
) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = await _user(session, clearer_id)
        await threads_service.clear(session, user, thread_id)


async def _seen_by(
    engine: AsyncEngine, user_id: uuid.UUID, thread_id: uuid.UUID
) -> list[uuid.UUID]:
    """The messages `user_id` is shown, through the messages page itself."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = await _user(session, user_id)
        page = await messages_service.list_messages(
            session, user, thread_id, PageParams(cursor=None, limit=50)
        )
    return [item.id for item in page.items]


async def _both(*steps: Awaitable[Any]) -> list[Any]:
    tasks = [asyncio.ensure_future(step) for step in steps]
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _cleared_at(engine: AsyncEngine, thread_id: uuid.UUID) -> datetime | None:
    async with AsyncSession(engine) as session:
        found: datetime | None = await session.scalar(
            select(ThreadClear.cleared_at).where(ThreadClear.thread_id == thread_id)
        )
    return found


def _patch_lock(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    name: str,
    *,
    before: Callable[[AsyncSession], Awaitable[None]] | None = None,
    after: Callable[[AsyncSession], Awaitable[None]] | None = None,
) -> None:
    """`module.name`, the call that takes the Thread's row, with a step before
    and after it. `messages.repository.thread_of` locks only with `lock`."""
    real = getattr(module, name)

    async def patched(session: AsyncSession, *args: Any, **kw: Any) -> Any:
        locks = name != "thread_of" or kw.get("lock")
        if locks and before is not None:
            await before(session)
        found = await real(session, *args, **kw)
        if locks and after is not None:
            await after(session)
        return found

    monkeypatch.setattr(module, name, patched)


async def test_a_message_waiting_on_a_clearing_shows(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The clearing holds the Thread; the send waits for it, then writes."""
    sender, clearer, thread_id = pair
    holding = asyncio.Event()
    send_pid: list[int] = []
    waited: list[bool] = []

    async def hold_until_the_send_waits(session: AsyncSession) -> None:
        holding.set()
        while not send_pid:
            await asyncio.sleep(0.01)
        await _blocked(test_engine, send_pid[0])
        waited.append(True)

    async def note_pid(session: AsyncSession) -> None:
        send_pid.append(await _pid(session))

    _patch_lock(
        monkeypatch, threads_repository, "lock_mine", after=hold_until_the_send_waits
    )
    _patch_lock(monkeypatch, messages_repository, "thread_of", before=note_pid)

    async def send_once_held() -> Any:
        await holding.wait()
        return await _send(test_engine, test_redis, sender, thread_id)

    _, sent = await _both(_clear(test_engine, clearer, thread_id), send_once_held())

    assert waited == [True]
    assert await _seen_by(test_engine, clearer, thread_id) == [sent.id]


async def test_a_message_a_clearing_waited_on_is_hidden(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The send holds the Thread; the clearing waits for it, and so clears
    what it wrote: the message existed when the clearing ran."""
    sender, clearer, thread_id = pair
    holding = asyncio.Event()
    clear_pid: list[int] = []
    waited: list[bool] = []

    async def hold_until_the_clearing_waits(session: AsyncSession) -> None:
        holding.set()
        while not clear_pid:
            await asyncio.sleep(0.01)
        await _blocked(test_engine, clear_pid[0])
        waited.append(True)

    async def note_pid(session: AsyncSession) -> None:
        clear_pid.append(await _pid(session))

    _patch_lock(
        monkeypatch,
        messages_repository,
        "thread_of",
        after=hold_until_the_clearing_waits,
    )
    _patch_lock(monkeypatch, threads_repository, "lock_mine", before=note_pid)

    async def clear_once_held() -> None:
        await holding.wait()
        await _clear(test_engine, clearer, thread_id)

    sent, _ = await _both(
        _send(test_engine, test_redis, sender, thread_id), clear_once_held()
    )

    assert waited == [True]
    assert await _seen_by(test_engine, clearer, thread_id) == []
    assert await _cleared_at(test_engine, thread_id) == sent.created_at
    assert await _seen_by(test_engine, sender, thread_id) == [sent.id]


async def test_a_message_begun_before_a_clearing_and_written_after_shows(
    test_engine: AsyncEngine,
    test_redis: Redis,
    pair: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The send's transaction begins, fixing its `now()`, the message's
    `created_at`; the clearing runs and commits; only then does the send take
    the Thread and write. A clearing stamped with its own time would hide it."""
    sender, clearer, thread_id = pair
    begun = asyncio.Event()
    cleared = asyncio.Event()
    send_now: list[datetime] = []
    clear_now: list[datetime] = []

    async def begin_then_wait_for_the_clearing(session: AsyncSession) -> None:
        began = await session.scalar(text("SELECT now()"))
        assert isinstance(began, datetime)
        send_now.append(began)
        begun.set()
        await cleared.wait()

    async def note_now(session: AsyncSession) -> None:
        now = await session.scalar(text("SELECT now()"))
        assert isinstance(now, datetime)
        clear_now.append(now)

    _patch_lock(
        monkeypatch,
        messages_repository,
        "thread_of",
        before=begin_then_wait_for_the_clearing,
    )
    _patch_lock(monkeypatch, threads_repository, "lock_mine", after=note_now)

    async def clear_once_begun() -> None:
        await begun.wait()
        await _clear(test_engine, clearer, thread_id)
        cleared.set()

    sent, _ = await _both(
        _send(test_engine, test_redis, sender, thread_id), clear_once_begun()
    )

    # The premise: the message is stamped before the clearing's own time.
    assert sent.created_at == send_now[0] < clear_now[0]
    assert await _seen_by(test_engine, clearer, thread_id) == [sent.id]
