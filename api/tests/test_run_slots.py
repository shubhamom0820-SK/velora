"""Each test run has a database and a Redis database of its own (P-55).

Every checkout on this machine shares one Postgres and one Redis. When runs
shared `velora_test` and Redis database 1, two runs at once failed each other's
tests: on 3 October 2026, two full runs started together failed 45 and 42
tests that pass alone. These tests take a second run's slot beside this one and
check that neither run sees the other's keys or rows, that a slot always starts
empty, and that a run killed outright frees its slot.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Sequence

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.infra import (
    API_DIR,
    DATABASE_OVERRIDE,
    RUN_SLOT,
    SERVER_URL,
    SLOTS,
    TEST_DATABASE_URL,
    TEST_REDIS_URL,
    RunSlot,
    SlotHolder,
    acquire_run_slot,
    requires_infra,
)

pytestmark = requires_infra


async def _take(slots: Sequence[int] = SLOTS, wait_s: float = 0) -> SlotHolder:
    return await asyncio.to_thread(
        lambda: acquire_run_slot(server_url=SERVER_URL, slots=slots, wait_s=wait_s)
    )


async def _release(holder: SlotHolder) -> None:
    await asyncio.to_thread(holder.release)


@pytest.fixture
async def other_run() -> AsyncIterator[RunSlot]:
    """A second run's slot, taken while this run holds its own."""
    holder = await _take()
    assert holder.slot is not None
    try:
        yield holder.slot
    finally:
        await _release(holder)


async def _leave_behind(slot: RunSlot) -> None:
    """What a run leaves in its slot: a Redis key, and a committed table."""
    redis = Redis.from_url(slot.redis_url)
    try:
        await redis.set("p55:left", "1")
    finally:
        await redis.aclose()
    engine = create_async_engine(slot.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("create table if not exists p55_left (id int)")
            )
    finally:
        await engine.dispose()


async def _left_in(slot: RunSlot) -> tuple[bool, bool]:
    """Whether the key and the table `_leave_behind` writes are there."""
    redis = Redis.from_url(slot.redis_url)
    try:
        key = await redis.exists("p55:left") == 1
    finally:
        await redis.aclose()
    engine = create_async_engine(slot.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            table = await connection.scalar(
                text("select to_regclass('p55_left') is not null")
            )
    finally:
        await engine.dispose()
    return key, bool(table)


async def test_this_run_is_on_its_own_slots_database_and_redis(
    db: AsyncSession, test_redis: Redis
) -> None:
    assert RUN_SLOT is not None
    if DATABASE_OVERRIDE is None:
        assert (
            make_url(TEST_DATABASE_URL).database == f"velora_slot{RUN_SLOT.number}_test"
        )
    assert (
        await db.scalar(text("select current_database()"))
        == make_url(TEST_DATABASE_URL).database
    )
    assert TEST_REDIS_URL.endswith(f"/{RUN_SLOT.number}")
    assert (await test_redis.client_info())["db"] == RUN_SLOT.number


async def test_a_second_run_at_once_has_its_own_slot_and_sees_none_of_this_runs_data(
    db: AsyncSession, test_redis: Redis, other_run: RunSlot
) -> None:
    assert RUN_SLOT is not None
    assert other_run.number != RUN_SLOT.number
    assert other_run.database_url != TEST_DATABASE_URL
    assert other_run.redis_url != TEST_REDIS_URL

    await test_redis.set("p55:mine", "1")
    theirs = Redis.from_url(other_run.redis_url)
    try:
        await theirs.set("p55:theirs", "1")
        seen_by_them = await theirs.exists("p55:mine")
        seen_by_me = await test_redis.exists("p55:theirs")
    finally:
        await theirs.aclose()
        await test_redis.delete("p55:mine")
    assert (seen_by_them, seen_by_me) == (0, 0)

    await _leave_behind(other_run)
    assert not await db.scalar(text("select to_regclass('p55_left') is not null"))


async def test_a_slot_starts_empty_whatever_its_last_run_left() -> None:
    first = await _take()
    assert first.slot is not None
    number = first.slot.number
    await _leave_behind(first.slot)
    assert await _left_in(first.slot) == (True, True)  # the probe works
    await _release(first)

    # The same slot again, as the next run to take it would.
    again = await _take(slots=(number,), wait_s=10)
    try:
        assert again.slot is not None
        assert await _left_in(again.slot) == (False, False)
    finally:
        await _release(again)


# The second run, as a process of its own: it takes a slot on import, says
# which, and waits to be killed.
_CHILD = (
    "import threading, tests.infra as infra; "
    "print(infra.RUN_SLOT.number, flush=True); "
    "threading.Event().wait()"
)


async def test_a_run_killed_outright_frees_its_slot() -> None:
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _CHILD,
        cwd=API_DIR,
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        assert child.stdout is not None
        number = int(await asyncio.wait_for(child.stdout.readline(), timeout=30))
        assert RUN_SLOT is not None and number != RUN_SLOT.number

        with pytest.raises(RuntimeError, match=r"is held by a running test run"):
            await _take(slots=(number,))
    finally:
        child.kill()  # SIGKILL: no atexit, no clean close
        await child.wait()

    freed = await _take(slots=(number,), wait_s=10)
    await _release(freed)
