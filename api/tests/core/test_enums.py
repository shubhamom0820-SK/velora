"""The Python enums and the database's enum types never drift apart.

Alembic's model comparison does not look at enum values, so without these tests
a value added to one side only would go unnoticed until a query failed.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PG_ENUMS

_DB_ENUMS = text(
    """
    select t.typname, array_agg(e.enumlabel order by e.enumsortorder)
    from pg_type t
    join pg_enum e on e.enumtypid = t.oid
    join pg_namespace n on n.oid = t.typnamespace
    where n.nspname = 'public'
    group by t.typname
    """
)


async def _database_enums(db: AsyncSession) -> dict[str, list[str]]:
    rows = (await db.execute(_DB_ENUMS)).all()
    return {name: list(labels) for name, labels in rows}


@pytest.mark.parametrize("pg_name", sorted(PG_ENUMS))
async def test_python_enum_matches_the_database(db: AsyncSession, pg_name: str) -> None:
    """Same values, same order — Postgres compares enums by position."""
    database = await _database_enums(db)

    assert pg_name in database, f"{pg_name} is missing from the database"
    assert [member.value for member in PG_ENUMS[pg_name]] == database[pg_name]


async def test_no_database_enum_without_a_python_twin(db: AsyncSession) -> None:
    database = await _database_enums(db)

    assert set(database) == set(PG_ENUMS)


def test_nineteen_enums_as_in_03_schema() -> None:
    """Twenty until P-25 made intent a catalogue (D-041)."""
    assert len(PG_ENUMS) == 19
