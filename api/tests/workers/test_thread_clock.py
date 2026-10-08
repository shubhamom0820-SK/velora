"""The Thread's clock (T-7.6): `expire_threads` and `warn_expiring`, the
worker's minute (D-640). Run on the `db` fixture's session through a
sessionmaker that hands it out, so every write rolls back; what they publish
is recorded by a Redis stand-in that refuses every command but PUBLISH."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, ThreadStatus
from app.modules.notifications.models import Notification
from app.modules.safety.models import Block
from app.modules.threads.models import Thread
from app.workers.tasks import thread_clock
from tests.conftest import MakeThread, MakeUser

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST


class Published:
    """Redis as the sweeps may use it: PUBLISH, recorded, and nothing else, so
    a run that reaches for any other command fails (D-640: the minute costs
    Redis only its events)."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(self, channel: str, message: str) -> int:
        envelope = json.loads(message)
        self.sent.append((channel, envelope["type"], envelope["data"]))
        return 1

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the sweep sent Redis {name.upper()}")


class Sessions:
    """A sessionmaker handing out the test's session, counting the batches."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.opened = 0

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        # As a fresh session would be: nothing open, and nothing the test
        # itself committed taken for the sweep's (session_for_the_app's way).
        if self.db.in_transaction():
            await self.db.commit()
        events.take_committed(self.db)
        self.opened += 1
        yield self.db


async def _expire(db: AsyncSession, redis: Published, **kw: Any) -> int:
    return await thread_clock.expire_threads(Sessions(db), redis, **kw)  # type: ignore[arg-type]


async def _warn(db: AsyncSession, redis: Published, **kw: Any) -> int:
    return await thread_clock.warn_expiring(Sessions(db), redis, **kw)  # type: ignore[arg-type]


async def _set(db: AsyncSession, thread_id: uuid.UUID, **values: Any) -> None:
    await db.execute(update(Thread).where(Thread.id == thread_id).values(**values))


async def _thread(db: AsyncSession, thread_id: uuid.UUID) -> Thread:
    found = await db.scalar(
        select(Thread)
        .where(Thread.id == thread_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _config(db: AsyncSession, key: str, value: int) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
        {"k": key, "v": str(value)},
    )


async def _notes(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, Any]]:
    rows = await db.scalars(select(Notification).where(Notification.user_id == user_id))
    return [(n.kind, n.payload) for n in rows]


# --- Expiry ---------------------------------------------------------------------------


async def test_a_thread_past_its_hour_is_expired_and_he_is_told(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    """D-560: the status catches the clock up; `thread.expired` to him, never
    to her (D-097)."""
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man)
    await _set(db, thread.id, expires_at=NOON)  # due at the instant itself
    redis = Published()

    assert await _expire(db, redis) == 1

    assert (await _thread(db, thread.id)).status is ThreadStatus.EXPIRED
    assert redis.sent == [
        (f"user:{man.id}", "thread.expired", {"thread_id": str(thread.id)})
    ]


async def test_what_isnt_due_is_left_alone(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    """A live Thread, a private message (no hour), a Knot, and one already
    expired: nothing moves and nobody is told."""
    clock.freeze(NOON)
    man, _ = await make_user()
    women = [(await make_user(Gender.FEMALE))[0] for _ in range(4)]
    live = await make_thread(man, women[0])
    await _set(db, live.id, expires_at=NOON + timedelta(seconds=1))
    dm = await make_thread(man, women[1], origin="dm")
    knot = await make_thread(man, women[2], status="knotted")
    expired = await make_thread(man, women[3], status="expired")
    redis = Published()

    assert await _expire(db, redis) == 0

    statuses = [
        (await _thread(db, each.id)).status for each in (live, dm, knot, expired)
    ]
    assert statuses == [
        ThreadStatus.ACTIVE,
        ThreadStatus.ACTIVE,
        ThreadStatus.KNOTTED,
        ThreadStatus.EXPIRED,
    ]
    assert redis.sent == []


async def test_it_works_in_batches_until_none_is_left(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    """Five due, batches of two: three transactions, every one expired."""
    clock.freeze(NOON)
    man, _ = await make_user()
    threads = []
    for _ in range(5):
        woman, _ = await make_user(Gender.FEMALE)
        thread = await make_thread(man, woman)
        await _set(db, thread.id, expires_at=NOON - timedelta(minutes=1))
        threads.append(thread.id)
    sessions = Sessions(db)
    redis = Published()

    expired = await thread_clock.expire_threads(sessions, redis, limit=2)  # type: ignore[arg-type]

    assert (expired, sessions.opened) == (5, 3)
    assert {(await _thread(db, each)).status for each in threads} == {
        ThreadStatus.EXPIRED
    }
    assert len(redis.sent) == 5


async def test_between_two_men_both_are_told(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    """D-554's allowlist: whoever sees the expiry, a man, is told of it; so a
    Thread between two men tells both (P-540 asks whether such a Thread
    should run on an hour at all)."""
    clock.freeze(NOON)
    one, _ = await make_user()
    two, _ = await make_user()
    thread = await make_thread(one, two)
    await _set(db, thread.id, expires_at=NOON - timedelta(minutes=1))
    redis = Published()

    await _expire(db, redis)

    assert sorted(channel for channel, _, _ in redis.sent) == sorted(
        [f"user:{one.id}", f"user:{two.id}"]
    )


# --- The warning ----------------------------------------------------------------------


async def test_ten_minutes_out_he_is_warned_once_and_she_never(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    """T-7.6's answer 2: one warning, `thread_warn_minutes` before expiry, to
    him only: an event and a notification (T-9.4 sends the push)."""
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man)
    expires = NOON + timedelta(minutes=10)
    await _set(db, thread.id, expires_at=expires)
    redis = Published()

    first = await _warn(db, redis)
    again = await _warn(db, redis)

    assert (first, again) == (1, 0)
    payload = {"thread_id": str(thread.id), "expires_at": expires.isoformat()}
    assert redis.sent == [(f"user:{man.id}", "thread.expiring", payload)]
    assert await _notes(db, man.id) == [("thread_expiring", payload)]
    assert await _notes(db, woman.id) == []
    assert (await _thread(db, thread.id)).expiry_warned_at == NOON


async def test_eleven_minutes_out_nobody_is_warned_yet(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _set(db, thread.id, expires_at=NOON + timedelta(minutes=11))

    assert await _warn(db, Published()) == 0
    assert (await _thread(db, thread.id)).expiry_warned_at is None


async def test_the_warning_reads_the_setting_never_a_number(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    await _config(db, "thread_warn_minutes", 20)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _set(db, thread.id, expires_at=NOON + timedelta(minutes=15))

    assert await _warn(db, Published()) == 1


async def test_a_thread_already_past_its_hour_is_never_warned(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _set(db, thread.id, expires_at=NOON)

    assert await _warn(db, Published()) == 0


async def test_each_new_expiry_gets_its_own_warning(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    """Every move of the hour clears the mark (D-560): warned for the first
    expiry, Extended, warned again when the new one nears."""
    from app.modules.threads import service as threads_service

    clock.freeze(NOON)
    man, _ = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    thread_id = thread.id
    await _set(db, thread_id, expires_at=NOON + timedelta(minutes=5))
    redis = Published()
    await _warn(db, redis)
    await db.commit()
    await threads_service.extend(db, man, thread_id, key="tap-0001", shown_price=10)

    clock.freeze(NOON + timedelta(hours=24))
    second = await _warn(db, redis)

    assert second == 1
    assert [kind for _, kind, _ in redis.sent] == ["thread.expiring"] * 2


async def test_a_minute_expires_first_and_then_warns(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    man, _ = await make_user()
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    due = await make_thread(man, one)
    near = await make_thread(man, two)
    await _set(db, due.id, expires_at=NOON - timedelta(seconds=1))
    await _set(db, near.id, expires_at=NOON + timedelta(minutes=2))
    redis = Published()

    done = await thread_clock.run({"sessionmaker": Sessions(db), "redis": redis})

    assert done == {"expired": 1, "warned": 1}
    assert [kind for _, kind, _ in redis.sent] == ["thread.expired", "thread.expiring"]


async def test_an_idle_minute_costs_redis_nothing(db: AsyncSession) -> None:
    """D-640: nothing due, nothing sent; `Published` refuses any other
    command, so a sweep that touched Redis would fail here."""
    redis = Published()

    done = await thread_clock.run({"sessionmaker": Sessions(db), "redis": redis})

    assert done == {"expired": 0, "warned": 0}
    assert redis.sent == []


# --- Across a block (T-9.1) -----------------------------------------------------------


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_across_a_block_nobody_is_warned(
    db: AsyncSession,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    who_blocks: str,
) -> None:
    """A warning about a Thread he can't open would tell him she blocked him;
    one about someone he blocked is about someone he chose not to see."""
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man)
    await _set(db, thread.id, expires_at=NOON + timedelta(minutes=10))
    blocker, blocked = (woman, man) if who_blocks == "her" else (man, woman)
    db.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    redis = Published()

    assert await _warn(db, redis) == 0

    assert redis.sent == []
    assert await _notes(db, man.id) == []
    assert (await _thread(db, thread.id)).expiry_warned_at is None


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_across_a_block_it_expires_and_nobody_is_told(
    db: AsyncSession,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    who_blocks: str,
) -> None:
    """The status catches the clock up all the same (D-560); no event."""
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man)
    await _set(db, thread.id, expires_at=NOON - timedelta(minutes=1))
    blocker, blocked = (woman, man) if who_blocks == "her" else (man, woman)
    db.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    redis = Published()

    assert await _expire(db, redis) == 1

    assert (await _thread(db, thread.id)).status is ThreadStatus.EXPIRED
    assert redis.sent == []


async def test_a_lifted_block_warns_and_tells_as_before(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man)
    await _set(db, thread.id, expires_at=NOON + timedelta(minutes=10))
    db.add(Block(blocker_id=woman.id, blocked_id=man.id, unblocked_at=NOON))
    redis = Published()

    assert await _warn(db, redis) == 1
    assert [kind for _, kind, _ in redis.sent] == ["thread.expiring"]
