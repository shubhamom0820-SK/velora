"""`get_session` yields a live session on the app's own database, holding one
connection for the whole request (P-52)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import QueuePool

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_sessionmaker, get_session
from app.core.providers import FakeProviders
from app.core.security import E164, make_access_token
from app.main import close_resources, create_app
from app.modules.users import service as users_service
from tests.conftest import make_test_settings
from tests.infra import TEST_DATABASE_URL, requires_infra
from tests.keys import random_keys

_TEST_DB_URL = "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora_test"
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
            DATABASE_URL=_TEST_DB_URL,
            REDIS_URL="redis://127.0.0.1:6379/1",
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
    assert response.json() == {"database": "velora_test"}


# --- One connection per request (P-52) ------------------------------------------
#
# The app as production builds it: its own get_session and pool on velora_test,
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
