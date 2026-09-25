"""Database-level guarantees from 03-SCHEMA.md.

T-1.8: extensions and the set_updated_at() trigger function. T-1.16 adds the
constraint tests (balance never negative, ledger append-only, and so on).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

EXTENSIONS = {"postgis", "pg_trgm", "pgcrypto", "citext"}


async def test_extensions_are_installed(db: AsyncSession) -> None:
    installed = set(
        (await db.execute(text("select extname from pg_extension"))).scalars()
    )

    assert installed >= EXTENSIONS


async def _table_with_the_trigger(db: AsyncSession) -> None:
    """A throwaway table wired up the way every mutable table will be (T-1.9+).
    Created inside the test's transaction, so it is rolled back with it."""
    await db.execute(
        text(
            """
            create table trigger_probe (
                id int primary key,
                note text,
                updated_at timestamptz not null default now()
            )
            """
        )
    )
    await db.execute(
        text(
            "create trigger trg_trigger_probe_updated_at before update on trigger_probe "
            "for each row execute function set_updated_at()"
        )
    )


async def test_set_updated_at_refreshes_the_column_on_update(db: AsyncSession) -> None:
    await _table_with_the_trigger(db)
    await db.execute(
        text("insert into trigger_probe values (1, 'first', '2000-01-01T00:00:00Z')")
    )

    await db.execute(text("update trigger_probe set note = 'second' where id = 1"))

    updated_at, now = (
        await db.execute(
            text("select updated_at, now() from trigger_probe where id = 1")
        )
    ).one()
    # now() is the transaction's start time, so the trigger's value equals it.
    assert updated_at == now


async def test_set_updated_at_leaves_inserts_alone(db: AsyncSession) -> None:
    """The trigger fires on UPDATE only; an explicit insert value is kept."""
    await _table_with_the_trigger(db)
    await db.execute(
        text("insert into trigger_probe values (1, 'first', '2000-01-01T00:00:00Z')")
    )

    updated_at = await db.scalar(
        text("select updated_at from trigger_probe where id = 1")
    )

    assert updated_at is not None
    assert updated_at.year == 2000
