"""Database engine, sessions, and the readiness check.

Each app owns its engine: `create_app()` builds it from the settings the app was
created with and keeps it on `app.state`, and the lifespan disposes it. There is
deliberately no process-wide engine — a global one read `get_settings()`, so an
app built with test settings silently connected to the dev database (P-05).

Building an engine opens no connection; the first query does. So an app starts
even when Postgres is down, and `/readyz` is what reports it.

Transactions are opened in the service layer (`async with session.begin():`);
repositories receive a session and never commit (`02-ARCHITECTURE.md` §2).
"""

from __future__ import annotations

import importlib.util
import pkgutil
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Any

from fastapi import Request
from sqlalchemy import DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column

from app.core.enums import PG_ENUMS

# Constraint names are deterministic, so migrations can drop and alter them by
# name and every environment ends up with identical names (03-SCHEMA.md).
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    """The one declarative base. Every table in every module's `models.py`
    subclasses it, so `Base.metadata` is the whole schema."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# --- Column helpers shared by every models.py (03-SCHEMA.md conventions) -------

_PG_NAME_OF = {cls: name for name, cls in PG_ENUMS.items()}


def pg_enum(enum_cls: type[StrEnum]) -> ENUM:
    """The column type for one of the enums T-1.8 created.

    `values_callable` makes SQLAlchemy store `'male'`, not the member name
    `'MALE'`, which the Postgres type would reject. `create_type=False` because
    the types are created by migration, never by SQLAlchemy.
    """
    return ENUM(
        enum_cls,
        name=_PG_NAME_OF[enum_cls],
        create_type=False,
        values_callable=lambda members: [m.value for m in members],
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    """`uuid primary key default gen_random_uuid()`."""
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def uuid_fk(
    target: str,
    *,
    nullable: bool = False,
    primary_key: bool = False,
    ondelete: str = "RESTRICT",
) -> MappedColumn[Any]:
    """A uuid foreign key. `on delete restrict` is the schema-wide default
    (03-SCHEMA.md): we don't hard-delete, so a dangling reference is a bug."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        primary_key=primary_key,
    )


class CreatedAt:
    """Every table: `created_at timestamptz not null default now()`."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Timestamps(CreatedAt):
    """Mutable tables also get `updated_at`, kept current by the
    `set_updated_at` trigger — the migration attaches it (T-1.8's function)."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# Tables Postgres extensions create for themselves (PostGIS's spatial_ref_sys).
# Not ours: autogenerate must never emit a DROP for them, and the models-match
# check must not count them as drift.
EXTENSION_OWNED_TABLES = frozenset({"spatial_ref_sys"})


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Alembic filter: ignore extension-owned tables."""
    return not (type_ == "table" and name in EXTENSION_OWNED_TABLES)


def import_models() -> None:
    """Import every `app/modules/*/models.py`, so `Base.metadata` is complete.

    A table is only in the metadata once its module has been imported. Without
    this, Alembic and the models-match test would silently ignore any module
    nothing else happened to import.
    """
    from app import modules

    for info in pkgutil.iter_modules(modules.__path__):
        if info.ispkg:
            name = f"app.modules.{info.name}.models"
            if importlib.util.find_spec(name) is not None:
                importlib.import_module(name)


def build_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, on this app's database."""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


async def check_database(engine: AsyncEngine) -> None:
    """Raise if Postgres cannot answer `SELECT 1`. Used only by `/readyz`."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
