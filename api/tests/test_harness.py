"""The harness itself: right database, nothing survives a test, and the app
under test shares the test's transaction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock as clock_module
from app.core.db import get_session
from tests.infra import (
    ensure_test_database,
    infra_policy,
    session_for_the_app,
    transactional_session,
)

# --- Which database -----------------------------------------------------------


async def test_db_is_the_test_database(db: AsyncSession) -> None:
    result = await db.execute(text("select current_database()"))

    assert result.scalar_one() == "velora_test"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora",
        "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora_test_copy",
        "postgresql+asyncpg://velora:velora@127.0.0.1:5432/",
    ],
)
def test_refuses_a_non_test_database(url: str) -> None:
    with pytest.raises(RuntimeError, match="must end in '_test'"):
        ensure_test_database(url)


def test_accepts_a_test_database() -> None:
    ensure_test_database("postgresql+asyncpg://velora:velora@ci-db:5432/velora_test")


# --- Nothing survives a test --------------------------------------------------


async def _table_exists(engine: AsyncEngine, name: str) -> bool:
    async with transactional_session(engine) as session:
        found = await session.execute(text("select to_regclass(:n)"), {"n": name})
        return found.scalar() is not None


async def test_writes_do_not_survive_the_transaction(test_engine: AsyncEngine) -> None:
    async with transactional_session(test_engine) as session:
        await session.execute(text("create table harness_probe (id int)"))
        await session.execute(text("insert into harness_probe values (1)"))
        assert await session.scalar(text("select count(*) from harness_probe")) == 1

    assert not await _table_exists(test_engine, "harness_probe")


async def test_a_commit_inside_the_transaction_is_still_rolled_back(
    test_engine: AsyncEngine,
) -> None:
    """Services commit. That must only release a savepoint, never escape."""
    async with transactional_session(test_engine) as session:
        await session.execute(text("create table harness_committed (id int)"))
        await session.commit()
        async with session.begin():
            await session.execute(text("insert into harness_committed values (1)"))

    assert not await _table_exists(test_engine, "harness_committed")


# --- The app shares the test's transaction ------------------------------------


async def test_client_sees_what_the_test_wrote_without_committing(
    db: AsyncSession, app: FastAPI, client: AsyncClient
) -> None:
    await db.execute(text("create table harness_shared (v text)"))
    await db.execute(text("insert into harness_shared values ('seen')"))

    @app.get("/v1/_test/shared")
    async def _shared(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str]:
        return {
            "v": (
                await session.execute(text("select v from harness_shared"))
            ).scalar_one()
        }

    response = await client.get("/v1/_test/shared")

    assert response.status_code == 200
    assert response.json() == {"v": "seen"}


async def test_a_route_cannot_reach_the_database_without_the_db_fixture(
    app: FastAPI, client: AsyncClient
) -> None:
    """Forgetting `db` must not mean writing to velora_test for real."""

    @app.get("/v1/_test/needs-db")
    async def _needs_db(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, int]:
        return {"one": (await session.execute(text("select 1"))).scalar_one()}

    response = await client.get("/v1/_test/needs-db")

    assert response.status_code == 500


async def test_the_app_session_refuses_when_no_db_fixture_is_active() -> None:
    with pytest.raises(RuntimeError, match="without the `db` fixture"):
        async for _ in session_for_the_app():
            pass


# --- Skip locally, fail in CI -------------------------------------------------


@pytest.mark.parametrize(
    ("reachable", "ci", "expected"),
    [
        (True, False, "run"),
        (True, True, "run"),
        (False, False, "skip"),
        (False, True, "fail"),
    ],
)
def test_infra_policy(reachable: bool, ci: bool, expected: str) -> None:
    assert infra_policy(reachable=reachable, ci=ci) == expected


# --- Clock ---------------------------------------------------------------------


def test_clock_fixture_freezes_and_advances(clock: ModuleType) -> None:
    clock.freeze(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(timedelta(hours=24))

    assert clock.now() == datetime(2026, 1, 2, tzinfo=UTC)


def test_clock_is_not_left_frozen() -> None:
    """Runs after the test above (pytest keeps file order) and checks that the
    `clock` fixture put the wall clock back."""
    assert clock_module.now().year >= 2026
    assert clock_module.now() != datetime(2026, 1, 2, tzinfo=UTC)
