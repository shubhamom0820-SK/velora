"""Test infrastructure: where this run's test database and Redis are, whether
they are safe and reachable, and the transaction every test runs inside.

Deliberately imports nothing from `app`: conftest calls this *before* it has made
the environment safe, and importing the app first would read settings early.

**Importing it takes a run slot (P-55).** Every checkout on this machine shares
one Postgres and one Redis. When two runs shared a database and a Redis
database, they failed each other's tests: on 3 October 2026, two full runs
started together failed 45 and 42 tests that pass alone. So each run holds a
slot, 2 to 15, for as long as its process lives, and the slot gives it a
database (`velora_slot<n>_test`) and a Redis database (`<n>`) nobody else uses.

The slot is a Postgres advisory lock on a connection this module keeps open,
so a run that crashes or is killed frees its slot when its connection closes:
nothing to clean up, no lease to expire. Taking a slot drops its database,
creates it empty and flushes its Redis database, so nothing a previous run
left (committed ledger rows, a weakened constraint, a migration stamp from
another branch) reaches this one.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import socket
import threading
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeVar
from urllib.parse import urlsplit

import pytest
from alembic.config import Config
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# Events only: it reads no settings, so importing it here is safe before
# conftest makes the environment safe.
from app.core import events

# The local stack's servers (`make infra-up`). Test-only, not app config, so
# they live here and in 06-TESTING.md, not in 02-ARCHITECTURE §11.
LOCAL_POSTGRES_URL = "postgresql+asyncpg://velora:velora@127.0.0.1:5432/postgres"
LOCAL_REDIS_URL = "redis://127.0.0.1:6379"

# A database of your own instead of the slot's. It is still refused unless its
# name ends in `_test`, and the run still takes a slot, for its Redis database.
DATABASE_OVERRIDE = os.environ.get("TEST_DATABASE_URL")

# Redis has 16 databases. 0 is `make dev`'s, and 1 is the test database every
# checkout shared before P-55, which a branch cut before it still uses.
SLOTS: Sequence[int] = range(2, 16)
# The advisory lock's first key, meaning "a test run's slot"; the second is the
# slot's number. Nothing else locks on it.
SLOT_LOCK = 55

T = TypeVar("T")


@dataclass(frozen=True)
class RunSlot:
    number: int
    database_url: str
    redis_url: str


def slot_database_url(server_url: str, number: int) -> str:
    return (
        make_url(server_url)
        .set(database=f"velora_slot{number}_test")
        .render_as_string(hide_password=False)
    )


def slot_redis_url(redis_url: str, number: int) -> str:
    return f"{redis_url}/{number}"


class SlotHolder:
    """Holds one slot: a connection to the server, kept open on an event loop
    of its own in a daemon thread. pytest's loop doesn't exist yet when this
    module is imported, and the lock must outlive every loop the run makes.
    When the process ends, the connection closes and Postgres frees the lock."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(
            target=self._loop.run_forever, name="test-run-slot", daemon=True
        ).start()
        self._engine: AsyncEngine | None = None
        self._connection: AsyncConnection | None = None
        self._released = False
        self.slot: RunSlot | None = None

    def _run(self, coroutine: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(
            timeout=60
        )

    def release(self) -> None:
        """Free the slot now, as the process ending would."""
        if self._released:
            return
        self._released = True
        self._run(self._close())
        self._loop.call_soon_threadsafe(self._loop.stop)

    async def _close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        if self._engine is not None:
            await self._engine.dispose()

    async def _take(
        self,
        server_url: str,
        redis_url: str,
        database_override: str | None,
        slots: Sequence[int],
        wait_s: float,
    ) -> RunSlot:
        self._engine = create_async_engine(
            server_url, poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        self._connection = connection = await self._engine.connect()
        number = await _lock_a_slot(connection, slots, wait_s)
        slot = RunSlot(
            number,
            database_override or slot_database_url(server_url, number),
            slot_redis_url(redis_url, number),
        )
        if database_override is None:
            name = make_url(slot.database_url).database
            # FORCE ends connections a dead run's processes left behind.
            await connection.execute(
                text(f'drop database if exists "{name}" with (force)')
            )
            await connection.execute(text(f'create database "{name}"'))
        redis = Redis.from_url(slot.redis_url)
        try:
            await redis.flushdb()
        finally:
            await redis.aclose()
        return slot


async def _lock_a_slot(
    connection: AsyncConnection, slots: Sequence[int], wait_s: float
) -> int:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s
    while True:
        for number in slots:
            locked = await connection.scalar(
                text("select pg_try_advisory_lock(:lock, :slot)"),
                {"lock": SLOT_LOCK, "slot": number},
            )
            if locked:
                return number
        if loop.time() >= deadline:
            raise RuntimeError(
                f"Every test slot ({', '.join(map(str, slots))}) is held by a "
                "running test run (P-55). Wait for one to finish: a run that "
                "crashed frees its slot as soon as Postgres sees its connection "
                "close."
            )
        await asyncio.sleep(0.1)


def acquire_run_slot(
    *,
    server_url: str = LOCAL_POSTGRES_URL,
    redis_url: str = LOCAL_REDIS_URL,
    database_override: str | None = None,
    slots: Sequence[int] = SLOTS,
    wait_s: float = 0,
) -> SlotHolder:
    """Take the first free slot of `slots`, waiting up to `wait_s` for one, and
    empty its database and Redis database. Held until `release()` or the
    process ends."""
    holder = SlotHolder()
    try:
        holder.slot = holder._run(
            holder._take(server_url, redis_url, database_override, slots, wait_s)
        )
    except BaseException:
        holder.release()
        raise
    return holder


def ensure_test_database(url: str) -> None:
    """Refuse any database whose name does not end in `_test`.

    Tests create tables and write rows. Pointed at the dev database — by an
    exported `DATABASE_URL`, a typo, or a copied config — they would do it there.
    """
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database {name!r}: the test database's "
            "name must end in '_test'. Set TEST_DATABASE_URL to a test database."
        )


def _reachable(url: str) -> bool:
    parts = urlsplit(url)
    if parts.hostname is None or parts.port is None:
        return False
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=0.5):
            return True
    except OSError:
        return False


def in_ci() -> bool:
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false")


InfraDecision = Literal["run", "skip", "fail"]


def infra_policy(*, reachable: bool, ci: bool) -> InfraDecision:
    """Locally, tests that need Postgres/Redis skip when they are down. In CI a
    missing database is an error, never a quiet skip: the wallet concurrency and
    ledger tests are exactly the ones that must not silently not run."""
    if reachable:
        return "run"
    return "fail" if ci else "skip"


def _server_url() -> str:
    """The server whose slots this run takes: the override's, or the local stack's."""
    if DATABASE_OVERRIDE is None:
        return LOCAL_POSTGRES_URL
    return (
        make_url(DATABASE_OVERRIDE)
        .set(database="postgres")
        .render_as_string(hide_password=False)
    )


SERVER_URL = _server_url()

# A bare TCP connect, deliberately not the app's own checks: a bug in
# check_database() must fail its test, not skip it.
INFRA_UP = _reachable(SERVER_URL) and _reachable(LOCAL_REDIS_URL)
INFRA_DOWN_REASON = "Postgres or Redis not reachable — start them with `make infra-up`"

RUN_SLOT_HOLDER = (
    acquire_run_slot(server_url=SERVER_URL, database_override=DATABASE_OVERRIDE)
    if INFRA_UP
    else None
)
if RUN_SLOT_HOLDER is not None:
    atexit.register(RUN_SLOT_HOLDER.release)
RUN_SLOT = RUN_SLOT_HOLDER.slot if RUN_SLOT_HOLDER is not None else None

# With nothing reachable every test that needs either skips, so these only have
# to look like what they would have been: the first slot's.
TEST_DATABASE_URL = (
    RUN_SLOT.database_url
    if RUN_SLOT is not None
    else DATABASE_OVERRIDE or slot_database_url(SERVER_URL, SLOTS[0])
)
TEST_REDIS_URL = (
    RUN_SLOT.redis_url
    if RUN_SLOT is not None
    else slot_redis_url(LOCAL_REDIS_URL, SLOTS[0])
)

requires_infra = pytest.mark.skipif(not INFRA_UP, reason=INFRA_DOWN_REASON)

# The local S3, standing in for R2 (T-4.1, D-086: SeaweedFS): only the storage
# tests need it, so it isn't part of INFRA_UP. The same rule applies: skip
# locally when it's down, fail in CI. Every run shares its two buckets (P-55
# gives it no slot), so each test writes under a prefix of its own.
LOCAL_S3_URL = "http://127.0.0.1:9000"
S3_UP = _reachable(LOCAL_S3_URL)
S3_DOWN_REASON = "The local S3 isn't reachable — start it with `make infra-up`"


# The face models (D-088, T-4.5): fetched, never committed (`make models`; CI
# fetches them before the tests). The same rule again: skip locally when they
# aren't there, fail in CI, where the real face match must never quietly not run.
MODELS_DOWN_REASON = (
    "The face models aren't in api/models — fetch them with `make models`"
)


def require_models() -> None:
    """Call first in a test that runs the real models."""
    from app.core import facemodels

    decision = infra_policy(reachable=not facemodels.problems(), ci=in_ci())
    if decision == "skip":
        pytest.skip(MODELS_DOWN_REASON)
    if decision == "fail":
        pytest.fail(f"CI requires the face models ({MODELS_DOWN_REASON}).")


@asynccontextmanager
async def transactional_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is always rolled back.

    `create_savepoint` means code under test can `commit()` or open
    `session.begin()` freely — that only ever touches a savepoint, and the outer
    transaction is discarded at the end. Postgres rolls back DDL too, so even
    tables a test creates disappear.
    """
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            if outer.is_active:
                await outer.rollback()


class ActiveSession:
    """The current test's session, for the app's `get_session` override, and
    what its requests published (P-64).

    A plain holder rather than a ContextVar: fixtures and the test body run in
    different tasks, so a ContextVar set in `db` would not be seen by requests.
    """

    session: AsyncSession | None = None
    published: ClassVar[list[events.Event]] = []


async def session_for_the_app(request: Request) -> AsyncIterator[AsyncSession]:
    """Stands in for `get_session` in tests: the `db` fixture's session, or a
    loud refusal — a test that forgets `db` must not write for real.

    When the request ends it publishes the events the request's committed
    transactions queued, to the app's Redis, as `get_session` does (P-64), and
    keeps them for the `published` fixture. What the test itself committed
    before the request is no request's, and is never published."""
    session = ActiveSession.session
    if session is None:
        raise RuntimeError(
            "This test reached the database without the `db` fixture. Request "
            "`db` so its writes are rolled back."
        )
    # A real request starts on a fresh session with no transaction open, and a
    # service opens its own (`async with session.begin()`). A test that wrote
    # through `db` first leaves one open, and begin() would refuse; end it, as
    # a new request would find it. Here a commit only releases a savepoint:
    # the test's outer transaction still rolls everything back.
    if session.in_transaction():
        await session.commit()
    events.take_committed(session)
    try:
        yield session
    finally:
        committed = events.take_committed(session)
        ActiveSession.published.extend(committed)
        await events.publish(committed, request.app.state.redis)


API_DIR = Path(__file__).resolve().parent.parent


async def run_alembic(
    engine: AsyncEngine, command: Callable[..., object], *args: str
) -> None:
    """Run an Alembic command (`alembic.command.upgrade`, `.downgrade`, …) on
    `engine`'s database from inside the running event loop.

    The connection is handed to env.py, which uses it instead of calling
    `asyncio.run()` — not allowed here, since pytest's loop is already running.
    """

    def _run(connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = connection
        command(config, *args)

    async with engine.begin() as connection:
        await connection.run_sync(_run)
