"""Migration 5978faceb05b (T-8.9, D-653): a gift send keeps its sender's
`Idempotency-Key`, one per sender. A send from before it gets its own id as its
key, so the upgrade works with rows in place, and going back keeps every send
(rule 12), dropping only the key.

Alembic runs on the test's own connection, inside its transaction, so all of
it rolls back (as test_reason_migration.py does).
"""

from __future__ import annotations

from collections.abc import Callable

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import Gender
from tests.conftest import MakeUser
from tests.infra import API_DIR

REVISION = "5978faceb05b"
BEFORE = "959e7af5110e"  # the revision 5978faceb05b follows


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
            "select column_name from information_schema.columns "
            "where table_name = 'gift_sends'"
        )
    )
    return set(rows)


async def test_a_send_from_before_gets_its_id_as_its_key_and_going_back_keeps_it(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _alembic(db, command.downgrade, BEFORE)
    assert "idempotency_key" not in await _columns(db)
    send_id = await db.scalar(
        text(
            "insert into gift_sends (sender_id, recipient_id, gift_id) "
            "values (:s, :r, 'rose') returning id"
        ),
        {"s": man.id, "r": woman.id},
    )

    await _alembic(db, command.upgrade, REVISION)

    key, nullable = (
        await db.execute(
            text(
                "select s.idempotency_key, c.is_nullable from gift_sends s, "
                "information_schema.columns c where s.id = :id "
                "and c.table_name = 'gift_sends' and c.column_name = 'idempotency_key'"
            ),
            {"id": send_id},
        )
    ).one()
    assert (key, nullable) == (str(send_id), "NO")

    await _alembic(db, command.downgrade, BEFORE)

    assert "idempotency_key" not in await _columns(db)
    assert (
        await db.scalar(
            text("select count(*) from gift_sends where id = :id"), {"id": send_id}
        )
        == 1
    )
