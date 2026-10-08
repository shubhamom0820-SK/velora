"""T-5.2's two ledger reasons (D-251): migration 4a7e20790605 rebuilds
`ledger_reason_t` with `thread_extend` and `dm_message`, both ways, keeping
every CHECK and index that reads `reason` exactly as it stood.

The round trip in test_migrations.py can't see a downgrade that leaves the two
values behind: on its way to base it drops the type outright. So this goes down
to the revision before and reads the type, and the definitions, back.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from alembic import command
from app.core.enums import Gender, LedgerReason
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType
from tests.conftest import MakeUser
from tests.infra import API_DIR, run_alembic

BEFORE = "190d7bebf133"  # only men hold credits (T-5.1)
RETYPE = "4a7e20790605"  # the two reasons

# ledger_reason_t as T-1.12 made it, in its order.
FIFTEEN = [
    "purchase",
    "purchase_bonus",
    "referral_reward",
    "admin_grant",
    "refund",
    "gift",
    "refund_banned_partner",
    "refund_album_declined",
    "thread_open",
    "dm_open",
    "thread_reopen",
    "voice_unlock",
    "album_request",
    "super_like",
    "liked_you_reveal",
]


async def _labels(connection: AsyncConnection) -> list[str]:
    """By name, never a `::regtype` literal: a prepared statement keeps the OID
    it was prepared with, which is the dropped type after one rebuild (the
    migration says more)."""
    rows = await connection.scalars(
        text(
            "select e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid "
            "where t.typname = 'ledger_reason_t' and pg_type_is_visible(t.oid) "
            "order by e.enumsortorder"
        )
    )
    return list(rows)


async def _ledger_shape(connection: AsyncConnection) -> dict[str, str]:
    """Every CHECK and index on `ledger_entries`, by name, as the database
    holds it."""
    checks = await connection.execute(
        text(
            "select conname, pg_get_constraintdef(oid) from pg_constraint "
            "where conrelid = to_regclass('ledger_entries') and contype = 'c'"
        )
    )
    indexes = await connection.execute(
        text(
            "select indexname, indexdef from pg_indexes "
            "where tablename = 'ledger_entries'"
        )
    )
    return dict([*checks.tuples(), *indexes.tuples()])


async def _read(engine: AsyncEngine) -> tuple[list[str], dict[str, str]]:
    async with engine.connect() as connection:
        return await _labels(connection), await _ledger_shape(connection)


async def test_the_reasons_go_down_and_up_and_keep_what_stood(
    test_engine: AsyncEngine,
) -> None:
    try:
        head = await _read(test_engine)
        await run_alembic(test_engine, command.downgrade, BEFORE)
        before = await _read(test_engine)
        await run_alembic(test_engine, command.upgrade, RETYPE)
        retyped = await _read(test_engine)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")
    after = await _read(test_engine)

    assert before[0] == FIFTEEN
    assert retyped[0] == [*FIFTEEN, "thread_extend", "dm_message"]
    # The rebuild re-created every CHECK and index exactly as it stood.
    assert retyped[1] == before[1]
    assert "ck_ledger_entries_ref_required" in before[1]
    assert after == head


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    """Alembic on the test's own connection, inside its transaction, so all of
    it rolls back (as test_guards.py does for D-076's migration)."""
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


async def _extend(db: AsyncSession, make_user: MakeUser) -> None:
    man, _ = await make_user(Gender.MALE, credits=10)
    await wallet_service.debit(
        db,
        man.id,
        10,
        LedgerReason.THREAD_EXTEND,
        ref=Ref(RefType.THREAD, uuid.uuid4()),
        event="extend-1",
    )


async def test_the_reasons_refuse_to_go_down_once_the_ledger_holds_one(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The ledger keeps every row (T-1.12), so a reason in use can't leave the
    type. To reach this migration's own refusal, the shape that would refuse
    first (next test) is taken away and the database stamped back past it."""
    await _extend(db, make_user)
    await db.execute(
        text(
            "alter table ledger_entries "
            "drop constraint ck_ledger_entries_reason_direction, "
            "drop constraint ck_ledger_entries_reason_ref_type"
        )
    )
    await db.execute(text("drop index uq_ledger_entries_one_per_event"))
    await _alembic(db, command.stamp, RETYPE)

    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert str(refused.value) == (
        "1 ledger entries use thread_extend or dm_message, and the ledger keeps "
        "every row (T-1.12), so they can't leave ledger_reason_t (D-251)"
    )
    # Right after the fifteen, whatever later migrations added after them.
    assert (await _labels(await db.connection()))[15:17] == [
        "thread_extend",
        "dm_message",
    ]


async def test_with_the_shape_in_place_its_check_refuses_first(
    db: AsyncSession, make_user: MakeUser
) -> None:
    await _extend(db, make_user)

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert "ck_ledger_entries_reason_direction" in str(refused.value)
