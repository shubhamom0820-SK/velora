"""Migrations 57ab54709630 and 652c4bad186e (T-8.4): `album_copies` (D-730),
whose downgrade refuses while a copy is recorded, since the row is the only
record of where the file is; and `album_reask_days` (D-731), 30, whose
downgrade removes exactly that key.

Alembic runs on the test's own connection, inside its transaction, so all of
it rolls back (as the gifts' migration test does).
"""

from __future__ import annotations

import uuid
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
from tests.modules.album.support import album_of

COPIES, REASK = "57ab54709630", "652c4bad186e"
BEFORE = "b53383c8e9b6"  # the revision 57ab54709630 follows


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


async def _tables(db: AsyncSession) -> set[str]:
    return set(await db.scalars(text("select tablename from pg_tables")))


async def _keys(db: AsyncSession) -> set[str]:
    return set(await db.scalars(text("select key from app_config")))


async def test_both_go_back_and_come_again_when_nothing_is_recorded(
    db: AsyncSession,
) -> None:
    assert "album_copies" in await _tables(db)
    days = await db.scalar(
        text("select value::int from app_config where key = 'album_reask_days'")
    )
    assert days == 30
    # The keys as this revision left them: a later one's (T-9.4's
    # `low_balance_velas`) goes with its own downgrade.
    await _alembic(db, command.downgrade, REASK)
    keys = await _keys(db)

    await _alembic(db, command.downgrade, COPIES)
    assert await _keys(db) == keys - {"album_reask_days"}
    await _alembic(db, command.downgrade, BEFORE)
    assert "album_copies" not in await _tables(db)

    await _alembic(db, command.upgrade, REASK)

    assert "album_copies" in await _tables(db)
    assert await _keys(db) == keys


async def test_a_tuned_value_survives_the_insert_run_again(db: AsyncSession) -> None:
    await db.execute(
        text("update app_config set value = '7' where key = 'album_reask_days'")
    )
    await _alembic(db, command.downgrade, COPIES)
    await db.execute(
        text("insert into app_config (key, value) values ('album_reask_days', '7')")
    )

    await _alembic(db, command.upgrade, REASK)

    assert (
        await db.scalar(
            text("select value::int from app_config where key = 'album_reask_days'")
        )
        == 7
    )


async def test_the_downgrade_refuses_while_a_copy_is_recorded(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    [photo] = await album_of(db, woman, photos=1)
    request_id = await db.scalar(
        text(
            "insert into album_requests (requester_id, owner_id, status) "
            "values (:m, :w, 'granted') returning id"
        ),
        {"m": man.id, "w": woman.id},
    )
    await db.execute(
        text(
            "insert into album_copies (request_id, photo_id, owner_id, viewer_id, "
            "file_key) values (:r, :p, :w, :m, :k)"
        ),
        {
            "r": request_id,
            "p": photo.id,
            "w": woman.id,
            "m": man.id,
            "k": f"album/{request_id}/{uuid.uuid4()}.jpg",
        },
    )
    await _alembic(db, command.downgrade, COPIES)

    with pytest.raises(RuntimeError, match=r"1 watermarked album copies .* \(D-730\)"):
        await _alembic(db, command.downgrade, BEFORE)
