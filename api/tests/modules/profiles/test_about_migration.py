"""Migration ac292d16611f (P-851, D-951): the bio is optional. Both ways, and the way
down refused while a bio is shorter than the 40 characters it would need again.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command
from tests.conftest import MakeUser
from tests.infra import API_DIR, run_alembic

BEFORE = "7c8a628fd3d7"


async def _rule(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        rule = await connection.scalar(
            text(
                "select pg_get_constraintdef(oid) from pg_constraint "
                "where conname = 'ck_profiles_about_length'"
            )
        )
        assert isinstance(rule, str)
        return rule


async def test_it_goes_down_and_up_and_keeps_what_stood(
    test_engine: AsyncEngine,
) -> None:
    try:
        head = await _rule(test_engine)
        await run_alembic(test_engine, command.downgrade, BEFORE)
        before = await _rule(test_engine)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")

    assert await _rule(test_engine) == head
    # As Postgres keeps a BETWEEN.
    assert head == (
        "CHECK (((char_length(about) >= 1) AND (char_length(about) <= 300)))"
    )
    assert before == (
        "CHECK (((char_length(about) >= 40) AND (char_length(about) <= 300)))"
    )


async def _downgrade(db: AsyncSession, revision: str) -> None:
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        command.downgrade(config, revision)

    await connection.run_sync(_run)


async def test_the_way_down_is_refused_while_a_bio_is_short(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    await db.execute(
        text("update profiles set about = 'Chai.' where user_id = :id"),
        {"id": user.id},
    )

    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            await _downgrade(db, BEFORE)

    assert str(refused.value) == (
        "1 bios are shorter than 40 characters, and the rule before P-851 needs "
        "40: there is no truthful bio to put in their place (D-951)"
    )
