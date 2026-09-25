"""Migrations and models stay in step.

These run outside the per-test rollback: migrating is DDL on `velora_test`
itself. Each one leaves the database at head, where the harness put it.
"""

from __future__ import annotations

import sys

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.schema import CreateIndex, CreateTable

from alembic import command
from app.core.db import NAMING_CONVENTION, Base, import_models, include_object
from tests.infra import API_DIR, run_alembic


async def test_the_harness_migrated_the_test_database(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as conn:
        found = await conn.scalar(text("select to_regclass('alembic_version')"))

    assert found is not None


async def test_migrations_round_trip(test_engine: AsyncEngine) -> None:
    """Every migration's downgrade() works: up, all the way down, up again.

    From T-1.8 on this exercises each schema migration automatically.
    """
    await run_alembic(test_engine, command.upgrade, "head")
    await run_alembic(test_engine, command.downgrade, "base")
    await run_alembic(test_engine, command.upgrade, "head")


def _schema_drift(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={"compare_type": True, "include_object": include_object},
    )
    return list(compare_metadata(context, Base.metadata))


async def test_models_match_migrations(test_engine: AsyncEngine) -> None:
    """The SQLAlchemy models and the migrated database describe the same schema.

    Replaces the manual "models match" check in T-1.8 to T-1.13: any drift —
    a column in a model but not a migration, or the reverse — fails here.
    """
    import_models()

    async with test_engine.connect() as conn:
        drift = await conn.run_sync(_schema_drift)

    assert drift == []


def test_import_models_imports_every_models_module() -> None:
    """A models.py that import_models() missed would be invisible to Alembic
    and to the check above — which would then pass having looked at nothing."""
    import_models()

    on_disk = {
        "app.modules." + path.parent.name + ".models"
        for path in (API_DIR / "app" / "modules").glob("*/models.py")
    }

    assert on_disk <= set(sys.modules)


def test_constraints_are_named_by_convention() -> None:
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    parents = Table("parents", metadata, Column("id", Integer, primary_key=True))
    children = Table(
        "children",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey(parents.c.id)),
        Column("code", Integer),
        UniqueConstraint("code"),
        CheckConstraint("code > 0", name="code_positive"),
    )
    index = Index(None, children.c.parent_id)

    # Names come from the naming convention, not the dialect.
    ddl = str(CreateTable(children))
    index_ddl = str(CreateIndex(index))

    assert "CONSTRAINT pk_children PRIMARY KEY" in ddl
    assert "CONSTRAINT fk_children_parent_id_parents FOREIGN KEY" in ddl
    assert "CONSTRAINT uq_children_code UNIQUE" in ddl
    assert "CONSTRAINT ck_children_code_positive CHECK" in ddl
    assert "INDEX ix_children_parent_id" in index_ddl


def test_extension_owned_tables_are_ignored() -> None:
    """Autogenerate must never try to DROP PostGIS's spatial_ref_sys."""
    assert include_object(None, "spatial_ref_sys", "table", True, None) is False
    assert include_object(None, "users", "table", True, None) is True
