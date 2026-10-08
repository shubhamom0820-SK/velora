"""Migration ddf84381ef6c (D-550): an active private message may carry no
expiry, and going back refuses while one does, rather than inventing an expiry
for a conversation both people were told never ends.

Alembic runs on the test's own connection, inside its transaction, so all of
it rolls back (as test_reason_migration.py does).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import Gender
from tests.conftest import MakeThread, MakeUser
from tests.infra import API_DIR

BEFORE = "fb0a7ce8dd16"  # the revision ddf84381ef6c follows


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


async def test_going_back_refuses_while_a_private_message_is_active(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await make_thread(man, woman, origin="dm")

    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert str(refused.value) == (
        "1 active private-message Thread(s) never expire (D-231, D-550); "
        "T-1.10's rule can't hold them. Not downgrading."
    )


async def test_going_back_puts_t110s_rule_back(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    low, high = sorted((man.id, woman.id))
    await _alembic(db, command.downgrade, BEFORE)

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await db.execute(
                text(
                    "insert into threads (user_low, user_high, origin, opened_by) "
                    "values (:low, :high, 'dm', :low)"
                ),
                {"low": low, "high": high},
            )

    assert "ck_threads_active_expires" in str(refused.value)


# Migration 7ee6438868ed (T-7.6): the hour, and the two settings beside it.

BEFORE_THE_HOUR = "0e6719809c1b"
THE_HOUR = "7ee6438868ed"


async def _hour_settings(db: AsyncSession) -> dict[str, object]:
    rows = await db.execute(
        text(
            "select key, value from app_config where key in "
            "('thread_hours', 'thread_extend_hours', 'thread_warn_minutes')"
        )
    )
    return dict(rows.tuples().all())


async def test_the_hour_goes_back_to_a_day_and_returns(db: AsyncSession) -> None:
    await _alembic(db, command.downgrade, BEFORE_THE_HOUR)
    before = await _hour_settings(db)
    await _alembic(db, command.upgrade, THE_HOUR)
    after = await _hour_settings(db)

    assert before == {"thread_hours": 24}
    assert after == {
        "thread_hours": 1,
        "thread_extend_hours": 24,
        "thread_warn_minutes": 10,
    }
