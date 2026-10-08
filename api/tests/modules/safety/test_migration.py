"""Migration 4889c586aa2c (T-9.1, D-860): blocks keep their history. Down and
up again with only standing blocks keeps every one; the downgrade refuses
while a lifted block is recorded, since the old primary key holds one row per
pair and going back would delete it.

Alembic runs on the test's own connection, inside its transaction, so all of
it rolls back (as the album's migration test does).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import Gender
from tests.conftest import MakeUser
from tests.infra import API_DIR

HISTORY, BEFORE = "4889c586aa2c", "bb4531b1f569"


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


async def _columns(db: AsyncSession) -> set[str]:
    rows = await db.scalars(
        text(
            "select column_name from information_schema.columns where table_name = 'blocks'"
        )
    )
    return set(rows)


async def test_down_and_up_again_keeps_every_standing_block(
    db: AsyncSession, make_user: MakeUser
) -> None:
    me, _ = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    pair = {"a": me.id, "b": her.id}
    await db.execute(
        text("insert into blocks (blocker_id, blocked_id) values (:a, :b)"), pair
    )

    await _alembic(db, command.downgrade, BEFORE)
    assert await _columns(db) == {"blocker_id", "blocked_id", "created_at"}
    await _alembic(db, command.upgrade, HISTORY)

    assert await _columns(db) == {
        "id",
        "blocker_id",
        "blocked_id",
        "created_at",
        "unblocked_at",
    }
    count = await db.scalar(
        text(
            "select count(*) from blocks where blocker_id = :a and blocked_id = :b "
            "and unblocked_at is null and id is not null"
        ),
        pair,
    )
    assert count == 1


async def test_the_downgrade_refuses_while_a_lifted_block_is_recorded(
    db: AsyncSession, make_user: MakeUser
) -> None:
    me, _ = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    await db.execute(
        text(
            "insert into blocks (blocker_id, blocked_id, unblocked_at) "
            "values (:a, :b, now())"
        ),
        {"a": me.id, "b": her.id},
    )

    with pytest.raises(RuntimeError, match="1 lifted blocks are recorded"):
        await _alembic(db, command.downgrade, BEFORE)
