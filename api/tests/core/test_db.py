"""`get_session` yields a live session on the app's own database, holding one
connection for the whole request (P-52)."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import event, text
from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_connection
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import QueuePool

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.db import WITHHELD, build_engine, build_sessionmaker, get_session
from app.core.providers import FakeProviders
from app.core.security import E164, make_access_token
from app.main import close_resources, create_app
from app.modules.users import service as users_service
from tests.conftest import make_test_settings
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL, requires_infra
from tests.keys import random_keys
from tests.roundtrips import RoundTrips

_DEV_DB_URL = "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora"


@pytest.fixture
def global_settings_point_at_dev(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make the process-wide settings disagree with the app's, as they would
    for a developer whose shell exports their dev DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", _DEV_DB_URL)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@requires_infra
async def test_get_session_uses_the_apps_database_not_the_global_one(
    global_settings_point_at_dev: None,
) -> None:
    assert get_settings().DATABASE_URL == _DEV_DB_URL  # the trap is set

    app = create_app(
        Settings(
            _env_file=None,
            ENV="local",
            DATABASE_URL=TEST_DATABASE_URL,
            REDIS_URL=TEST_REDIS_URL,
            **random_keys(),  # type: ignore[arg-type]
        )
    )

    @app.get("/v1/_test/current-database")
    async def _current_database(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str]:
        result = await session.execute(text("select current_database()"))
        return {"database": result.scalar_one()}

    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/_test/current-database")
    finally:
        await close_resources(app)

    assert response.status_code == 200
    assert response.json() == {"database": make_url(TEST_DATABASE_URL).database}


# --- One connection per request (P-52) ------------------------------------------
#
# The app as production builds it: its own get_session and pool on the test database,
# no test transaction around it. Anything written is written for real, so the
# one test that needs rows creates and deletes them itself.


@pytest.fixture
async def real_app(test_redis: Redis) -> AsyncIterator[FastAPI]:
    application = create_app(make_test_settings())
    application.state.providers = FakeProviders().as_providers()
    try:
        yield application
    finally:
        await close_resources(application)


def _checkouts(app: FastAPI) -> list[int]:
    """A live count of connections taken from the app's pool."""
    count = [0]

    def checked_out(*_: object) -> None:
        count[0] += 1

    event.listen(app.state.engine.sync_engine.pool, "checkout", checked_out)
    return count


async def _call(app: FastAPI, method: str, path: str, **kwargs: Any) -> Response:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


async def test_two_transactions_in_a_request_share_one_connection(
    real_app: FastAPI,
) -> None:
    @real_app.get("/v1/_test/two-transactions")
    async def _two(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, int]:
        async with session.begin():
            first = await session.scalar(text("select 1"))
        async with session.begin():
            second = await session.scalar(text("select 2"))
        return {"sum": int(first or 0) + int(second or 0)}

    checkouts = _checkouts(real_app)

    response = await _call(real_app, "GET", "/v1/_test/two-transactions")

    assert response.json() == {"sum": 3}
    assert checkouts == [1]
    # And it went back to the pool when the request ended.
    assert real_app.state.engine.sync_engine.pool.checkedout() == 0


async def test_a_request_that_never_queries_takes_nothing_from_the_pool(
    real_app: FastAPI,
) -> None:
    """Checked out at the first query, not when the session is made: a flood of
    bad tokens never queues for a connection."""

    @real_app.get("/v1/_test/no-query")
    async def _no_query(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, bool]:
        return {"ok": True}

    checkouts = _checkouts(real_app)

    assert (await _call(real_app, "GET", "/v1/_test/no-query")).status_code == 200
    bad_token = await _call(
        real_app, "GET", "/v1/me", headers={"Authorization": "Bearer not.a.token"}
    )

    assert bad_token.status_code == 401
    assert checkouts == [0]


async def test_me_checks_out_once_for_current_user_and_the_route(
    real_app: FastAPI, test_engine: AsyncEngine
) -> None:
    """current_user's transaction and the route's, one connection between them.
    The rows are committed for real, then deleted."""
    settings = make_test_settings()
    phone = E164(f"+9198765{uuid.uuid4().int % 10**5:05d}")
    async with (
        AsyncSession(test_engine, expire_on_commit=False) as setup,
        setup.begin(),
    ):
        account = await users_service.create_account(setup, phone, settings)
    user_id = account.user.id
    token = make_access_token(
        user_id, account.user.role, settings, auth_time=clock.now()
    )
    checkouts = _checkouts(real_app)
    try:
        response = await _call(
            real_app, "GET", "/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
    finally:
        async with test_engine.begin() as conn:
            for table in ("notification_prefs", "wallets", "profiles"):
                await conn.execute(
                    text(f"delete from {table} where user_id = :u"), {"u": user_id}
                )
            await conn.execute(text("delete from users where id = :u"), {"u": user_id})

    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    assert checkouts == [1]


async def test_a_failed_transaction_still_returns_the_connection(
    real_app: FastAPI,
) -> None:
    @real_app.get("/v1/_test/fails")
    async def _fails(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> None:
        async with session.begin():
            await session.execute(text("select 1"))
            raise RuntimeError("boom")

    pool = real_app.state.engine.sync_engine.pool

    assert (await _call(real_app, "GET", "/v1/_test/fails")).status_code == 500
    assert pool.checkedout() == 0


@pytest.mark.parametrize("between_transactions", [False, True], ids=["mid", "between"])
@pytest.mark.parametrize("ending", ["close", "reset", "invalidate"])
async def test_every_way_a_session_ends_returns_its_connection(
    test_engine: AsyncEngine, ending: str, between_transactions: bool
) -> None:
    """Mid-transaction, ending the transaction would release it anyway; between
    transactions only the session itself knows it holds a connection."""
    engine = build_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    pool = engine.sync_engine.pool
    assert isinstance(pool, QueuePool)
    try:
        session = build_sessionmaker(engine)()
        if between_transactions:
            async with session.begin():
                await session.execute(text("select 1"))
        else:
            await session.execute(text("select 1"))
        assert pool.checkedout() == 1

        await getattr(session, ending)()

        assert pool.checkedout() == 0
    finally:
        await engine.dispose()


# --- The liveness check, only for idle connections (P-53) -------------------------

START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)


async def _one_request(maker: async_sessionmaker[AsyncSession]) -> int:
    """A request's transaction: one select between BEGIN and COMMIT. Returns
    the server process behind the connection, which names the connection."""
    async with maker() as session, session.begin():
        return int(await session.scalar(text("select pg_backend_pid()")) or 0)


async def _kill(test_engine: AsyncEngine, pid: int) -> None:
    """End a connection's server process and wait until it has gone."""
    async with test_engine.connect() as admin:
        await admin.execute(text("select pg_terminate_backend(:pid)"), {"pid": pid})
        await admin.commit()
        for _ in range(200):
            alive = await admin.scalar(
                text("select count(*) from pg_stat_activity where pid = :pid"),
                {"pid": pid},
            )
            # Postgres takes pg_stat_activity's snapshot once per transaction:
            # without ending it, every poll would read the first answer again.
            await admin.rollback()
            if not alive:
                return
            await asyncio.sleep(0.01)
    raise AssertionError("the server process didn't end")


@pytest.fixture
async def through_a_counter() -> AsyncIterator[tuple[RoundTrips, AsyncEngine]]:
    """An engine with one connection, its round trips counted."""
    async with RoundTrips() as trips:
        engine = build_engine(trips.url, pool_size=1, max_overflow=0)
        try:
            yield trips, engine
        finally:
            await engine.dispose()


async def test_a_warm_connection_is_handed_out_unchecked(
    through_a_counter: tuple[RoundTrips, AsyncEngine],
) -> None:
    """BEGIN, the select, COMMIT: three round trips. With `pool_pre_ping`, six:
    asyncpg's check wraps `;` in a BEGIN and a ROLLBACK of its own, 495 ms on
    staging, on every checkout (P-49)."""
    trips, engine = through_a_counter
    maker = build_sessionmaker(engine)
    for _ in range(2):  # connect, and prepare the statement
        await _one_request(maker)
    trips.reset()

    await _one_request(maker)

    assert trips.count == 3


async def test_a_connection_idle_for_30_seconds_is_checked_first(
    through_a_counter: tuple[RoundTrips, AsyncEngine], clock: ModuleType
) -> None:
    trips, engine = through_a_counter
    maker = build_sessionmaker(engine)
    clock.freeze(START)
    for _ in range(2):
        await _one_request(maker)

    clock.advance(timedelta(seconds=29, microseconds=999_999))
    trips.reset()
    await _one_request(maker)
    assert trips.count == 3

    # The check is BEGIN, `;` and ROLLBACK, then the request's three. The first
    # time on a connection asyncpg also prepares `;`, one round trip more.
    clock.advance(timedelta(seconds=30))
    trips.reset()
    await _one_request(maker)
    assert trips.count == 7

    clock.advance(timedelta(seconds=30))
    trips.reset()
    await _one_request(maker)
    assert trips.count == 6


async def test_a_dead_idle_connection_is_replaced_before_the_request_sees_it(
    test_engine: AsyncEngine, clock: ModuleType
) -> None:
    engine = build_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    maker = build_sessionmaker(engine)
    try:
        clock.freeze(START)
        pid = await _one_request(maker)
        await _kill(test_engine, pid)
        clock.advance(timedelta(seconds=30))

        assert await _one_request(maker) != pid
    finally:
        await engine.dispose()


async def test_a_connection_that_dies_within_30_seconds_fails_one_request(
    test_engine: AsyncEngine, clock: ModuleType
) -> None:
    """The price of not checking warm connections, pinned so nobody mistakes it
    for a bug: one that dies within 30 seconds of its last use fails the request
    that finds it. The pool then drops it, and the next request gets a new one."""
    engine = build_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    maker = build_sessionmaker(engine)
    try:
        clock.freeze(START)
        pid = await _one_request(maker)
        await _kill(test_engine, pid)
        clock.advance(timedelta(seconds=29))

        with pytest.raises(DBAPIError) as failed:
            await _one_request(maker)
        assert failed.value.connection_invalidated
        assert await _one_request(maker) != pid
    finally:
        await engine.dispose()


async def test_the_pool_hands_out_its_newest_connection_first() -> None:
    """So a quiet pool keeps reusing the connection it just used, which is warm
    and unchecked, rather than the one that has idled longest."""
    engine = build_engine(TEST_DATABASE_URL, pool_size=2, max_overflow=0)
    maker = build_sessionmaker(engine)
    try:
        older, newer = maker(), maker()
        await older.scalar(text("select pg_backend_pid()"))
        newer_pid = await newer.scalar(text("select pg_backend_pid()"))
        await older.close()
        await newer.close()  # back in the pool last

        async with maker() as next_request:
            assert (
                await next_request.scalar(text("select pg_backend_pid()")) == newer_pid
            )
    finally:
        await engine.dispose()


async def test_a_new_connection_is_never_checked(
    monkeypatch: pytest.MonkeyPatch, clock: ModuleType
) -> None:
    """It has just proved itself by connecting. Counted at the driver: the
    first request checks nothing; the first after 30 idle seconds, once."""
    pings: list[object] = []
    real_ping = AsyncAdapt_asyncpg_connection.ping

    def counted(self: AsyncAdapt_asyncpg_connection) -> None:
        pings.append(self)
        real_ping(self)  # type: ignore[no-untyped-call]  # SQLAlchemy's, untyped

    monkeypatch.setattr(AsyncAdapt_asyncpg_connection, "ping", counted)
    engine = build_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    maker = build_sessionmaker(engine)
    try:
        clock.freeze(START)
        await _one_request(maker)
        assert pings == []

        clock.advance(timedelta(seconds=30))
        await _one_request(maker)
        assert len(pings) == 1
    finally:
        await engine.dispose()


# Rule 15 at the database (P-80, D-990): every way a failed query's error
# quoted a value past SQLAlchemy's `hide_parameters`, each value short enough
# that asyncpg's 40-character cut can't hide it by luck.
_LEAKS = {
    "a duplicate key, in DETAIL": (
        "insert into leak (v, n) values (:v, 1)",
        True,
    ),
    "a check's failing row, in DETAIL": (
        "insert into leak (v, n) values (:v || '-2', -5)",
        False,
    ),
    "a cast Postgres refused, in its message": (
        "select cast(cast(:v as text) as integer)",
        False,
    ),
    "an argument asyncpg can't encode, in its message": (
        "select cast(:v as integer)",
        False,
    ),
}


async def _fail(
    engine: AsyncEngine, statement: str, value: str, seed: bool
) -> DBAPIError:
    async with engine.connect() as connection:
        await connection.execute(
            text("create temp table leak (v text unique, n int check (n > 0))")
        )
        if seed:
            await connection.execute(
                text("insert into leak (v, n) values (:v, 1)"), {"v": value}
            )
        with pytest.raises(DBAPIError) as failure:
            await connection.execute(text(statement), {"v": value})
    return failure.value


def _everything_it_prints(error: BaseException) -> str:
    """The whole chain, as a traceback in the logs shows it, and each layer's
    fields, as an error reporter would read them."""
    layers = [error, error.__cause__, getattr(error.__cause__, "__cause__", None)]
    fields = [repr(getattr(layer, "as_dict", dict)()) for layer in layers]
    return "".join(traceback.format_exception(error)) + "".join(fields)


@requires_infra
@pytest.mark.parametrize("leak", list(_LEAKS), ids=list(_LEAKS))
async def test_the_apis_database_errors_carry_no_values(
    real_app: FastAPI, leak: str
) -> None:
    statement, seed = _LEAKS[leak]
    value = f"v-{uuid.uuid4().hex[:12]}"
    parameters_only = create_async_engine(TEST_DATABASE_URL, hide_parameters=True)
    try:
        before = await _fail(parameters_only, statement, value, seed)
    finally:
        await parameters_only.dispose()
    after = await _fail(real_app.state.engine, statement, value, seed)

    assert value in _everything_it_prints(before)  # the check can see it
    assert value not in _everything_it_prints(after)


@requires_infra
async def test_a_withheld_error_keeps_its_code_and_constraint(
    real_app: FastAPI,
) -> None:
    """The services read both (`sqlstate_of`, a unique key's name)."""
    value = f"v-{uuid.uuid4().hex[:12]}"
    error = await _fail(
        real_app.state.engine, _LEAKS["a duplicate key, in DETAIL"][0], value, True
    )

    driver = error.__cause__.__cause__ if error.__cause__ else None

    assert users_service.sqlstate_of(error) == "23505"
    assert getattr(driver, "constraint_name", None) == "leak_v_key"
    assert getattr(driver, "detail", "absent") is None
    first_line = str(error).splitlines()[0]
    assert first_line.startswith(
        "(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) "
        "<class 'asyncpg.exceptions.UniqueViolationError'>: "
        'duplicate key value violates unique constraint "leak_v_key" [sqlstate=23505 '
    )
    assert first_line.endswith("table_name=leak constraint_name=leak_v_key]")
    assert "DETAIL" not in str(error)


@requires_infra
async def test_postgres_s_words_are_kept_only_where_they_quote_nothing(
    real_app: FastAPI,
) -> None:
    """Our triggers' wording is ours, and tests match it; a cast's names the
    text it refused, so it goes."""
    engine = real_app.state.engine
    async with engine.connect() as connection:
        with pytest.raises(DBAPIError) as ours:
            await connection.execute(
                text("do $$ begin raise exception 'leak % is ours', 3; end $$")
            )
    cast = await _fail(
        engine, _LEAKS["a cast Postgres refused, in its message"][0], "v-1", False
    )

    assert "leak 3 is ours [sqlstate=P0001]" in str(ours.value)
    assert f"{WITHHELD} [sqlstate=22P02]" in str(cast)
