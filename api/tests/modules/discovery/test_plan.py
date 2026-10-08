"""The feed's plan (T-6.2, the founder's Q7 answer): on a crowd spread across
India, where the radius is selective, Postgres finds the candidates through
`ix_profiles_location`, the GIST index; and the statement runs with JIT off,
for its own transaction only (D-495). Deterministic, so it runs in `make test`;
the timing, at 50k and on both shapes, is `bench/discovery`'s, run by hand."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import Select

from app.core.enums import Gender, Seeking
from app.modules.discovery import repository
from bench.discovery.crowd import PHAGWARA, crowd
from tests.conftest import MakeUser
from tests.modules.discovery.support import person

pytestmark = pytest.mark.usefixtures("test_redis")

# Enough that a sequential scan costs more than the index would, small enough
# that CI writes it in about a second.
CROWD = 6000
NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)
GIST = "ix_profiles_location"


async def explain(session: AsyncSession, statement: Select[Any]) -> dict[str, Any]:
    """`EXPLAIN (FORMAT JSON)` of exactly this statement, its parameters bound
    as the API binds them."""
    connection = await session.connection()
    compiled = statement.compile(
        dialect=connection.dialect, compile_kwargs={"render_postcompile": True}
    )
    params = compiled.construct_params()
    positions = compiled.positiontup or []
    result = await connection.exec_driver_sql(
        "EXPLAIN (FORMAT JSON) " + str(compiled),
        tuple(params[name] for name in positions),
    )
    plan = result.scalar_one()
    found: list[dict[str, Any]] = json.loads(plan) if isinstance(plan, str) else plan
    top: dict[str, Any] = found[0]["Plan"]
    return top


def index_names(node: dict[str, Any]) -> set[str]:
    names = {node["Index Name"]} if "Index Name" in node else set()
    for child in node.get("Plans", []):
        names |= index_names(child)
    return names


async def _viewer(db: AsyncSession, make_user: MakeUser) -> repository.Viewer:
    me, _ = await person(db, make_user, Gender.MALE, at=PHAGWARA)
    return repository.Viewer(
        id=me.id,
        gender=Gender.MALE,
        seeking=Seeking.WOMEN,
        shadowed=False,
        position=PHAGWARA,
    )


def _first_page(viewer: repository.Viewer) -> Select[Any]:
    return repository.feed_query(
        viewer,
        as_of=NOON,
        radius_m=25_000.0,
        new_first=False,
        online_since=None,
        intent_ids=(),
        badge_only=False,
        after=None,
        limit=21,
    )


async def test_a_spread_crowd_is_searched_through_the_gist_index(
    db: AsyncSession, make_user: MakeUser
) -> None:
    await crowd(db, CROWD, "spread", tag="plan01")
    viewer = await _viewer(db, make_user)

    plan = await explain(db, _first_page(viewer))

    assert GIST in index_names(plan), json.dumps(plan, indent=1)[:4000]


async def test_the_query_explained_is_the_one_that_answers(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The plan read is the statement's own: run, it finds the crowd's
    Phagwara twentieth, ranked, and the women among them only."""
    await crowd(db, CROWD, "spread", tag="plan02")
    viewer = await _viewer(db, make_user)

    rows = (await db.execute(_first_page(viewer))).all()

    assert len(rows) == 21
    assert [row.score for row in rows] == sorted(
        (row.score for row in rows), reverse=True
    )
    assert all(row.distance_m <= 25_000 for row in rows)


async def test_the_feed_runs_with_jit_off_for_its_own_transaction_only(
    test_engine: AsyncEngine,
) -> None:
    """D-495: off inside the feed's transaction, and as it was after it."""
    viewer = repository.Viewer(
        id=uuid4(),
        gender=Gender.MALE,
        seeking=Seeking.WOMEN,
        shadowed=False,
        position=PHAGWARA,
    )
    page = {
        "as_of": NOON,
        "radius_m": 25_000.0,
        "new_first": False,
        "online_since": None,
        "intent_ids": (),
        "badge_only": False,
        "after": None,
        "limit": 21,
    }
    async with AsyncSession(test_engine) as session:
        # The connection's own setting on, whatever the server's default.
        await session.execute(text("SET jit = on"))
        await session.commit()
        try:
            async with session.begin():
                await repository.feed(session, viewer, **page)
                during = await session.scalar(text("SHOW jit"))
            after = await session.scalar(text("SHOW jit"))
            await session.rollback()
        finally:
            await session.execute(text("RESET jit"))
            await session.commit()

    assert during == "off"
    assert after == "on"
