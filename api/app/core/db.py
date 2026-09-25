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
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

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
