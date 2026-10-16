"""Migration 7c8a628fd3d7 (T-9.5, D-922): a ban is lifted in place, never
deleted. Both ways; the way down refused once a ban has been lifted, since the
table before it has nowhere to keep a lift; and the app role able to write the
three lift columns and nothing else of a row.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command
from tests.conftest import MakeUser
from tests.infra import API_DIR, run_alembic

BEFORE = "7a758777affd"
LIFT = "7c8a628fd3d7"


async def _shape(engine: AsyncEngine) -> tuple[list[str], list[str], list[str]]:
    async with engine.connect() as connection:
        columns = await connection.scalars(
            text(
                "select column_name from information_schema.columns "
                "where table_name = 'banned_identities' order by column_name"
            )
        )
        indexes = await connection.scalars(
            text(
                "select indexdef from pg_indexes "
                "where tablename = 'banned_identities' order by indexname"
            )
        )
        grants = await connection.scalars(
            text(
                "select privilege_type from information_schema.role_table_grants "
                "where grantee = 'velora_app' and table_name = 'banned_identities' "
                "order by privilege_type"
            )
        )
        return list(columns), list(indexes), list(grants)


async def test_it_goes_down_and_up_and_keeps_what_stood(
    test_engine: AsyncEngine,
) -> None:
    try:
        head = await _shape(test_engine)
        await run_alembic(test_engine, command.downgrade, BEFORE)
        before = await _shape(test_engine)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")
    after = await _shape(test_engine)

    assert after == head
    assert {"lifted_at", "lifted_by", "lift_reason"} <= set(head[0])
    assert not {"lifted_at", "lifted_by", "lift_reason"} & set(before[0])
    assert any("WHERE (lifted_at IS NULL)" in index for index in head[1])
    # The app role keeps INSERT and SELECT, and UPDATE only on the lift columns.
    assert head[2] == ["INSERT", "SELECT"]
    assert before[2] == ["DELETE", "INSERT", "SELECT", "UPDATE"]


async def _alembic(db: AsyncSession, revision: str) -> None:
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        command.downgrade(config, revision)

    await connection.run_sync(_run)


async def test_the_way_down_is_refused_once_a_ban_was_lifted(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin, _ = await make_user()
    await db.execute(
        text(
            "insert into banned_identities (kind, value, reason, lifted_at, lifted_by, "
            "lift_reason) values ('phone_hash', 'h', 'ban', now(), :by, 'a mistake')"
        ),
        {"by": admin.id},
    )

    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            await _alembic(db, BEFORE)

    assert str(refused.value) == (
        "1 bans have been lifted, and the table before T-9.5 has nowhere to keep "
        "a lift: putting them back would ban those numbers again (D-922)"
    )


async def test_the_app_role_writes_only_the_lift_columns(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin, _ = await make_user()
    await db.execute(
        text(
            "insert into banned_identities (kind, value, reason) values ('phone_hash', 'h2', 'ban')"
        )
    )
    await db.execute(text("set local role velora_app"))

    with pytest.raises(DBAPIError) as refused:
        async with db.begin_nested():
            await db.execute(
                text("update banned_identities set reason = 'other' where value = 'h2'")
            )
    assert "permission denied" in str(refused.value)

    await db.execute(
        text(
            "update banned_identities set lifted_at = now(), lifted_by = :by, "
            "lift_reason = 'a mistake' where value = 'h2'"
        ),
        {"by": admin.id},
    )
    lifted = await db.scalar(
        text("select lifted_at is not null from banned_identities where value = 'h2'")
    )
    assert lifted is True
