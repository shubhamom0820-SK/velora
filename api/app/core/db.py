"""Database engine, sessions, and the readiness check.

Each app owns its engine: `create_app()` builds it from the settings the app was
created with and keeps it on `app.state`, and the lifespan disposes it. There is
deliberately no process-wide engine — a global one read `get_settings()`, so an
app built with test settings silently connected to the dev database (P-05).

Building an engine opens no connection; the first query does. So an app starts
even when Postgres is down, and `/readyz` is what reports it.

Transactions are opened in the service layer (`async with session.begin():`);
repositories receive a session and never commit (`02-ARCHITECTURE.md` §2). A
request may open several, one after another, on one connection (P-52).
"""

from __future__ import annotations

import importlib.util
import pkgutil
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from fastapi import Request
from sqlalchemy import DateTime, ForeignKey, MetaData, event, exc, func, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedColumn,
    Session,
    mapped_column,
)
from sqlalchemy.pool import ConnectionPoolEntry, PoolProxiedConnection

from app.core import clock, events
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


# A pooled connection is checked before it's handed out only if it has sat idle
# this long (P-53). The check is asyncpg's: BEGIN, `;`, ROLLBACK, three round
# trips (four the first time on a connection, which prepares `;`), 495 ms from
# Singapore to Mumbai (P-49), where `pool_pre_ping` paid them on every checkout. A warm connection is handed out unchecked; one that died
# within this window fails the request that finds it, and the pool replaces it.
CHECK_IF_IDLE_FOR = timedelta(seconds=30)
_CHECKED_IN_AT = "checked_in_at"


def build_engine(url: str, *, pool_size: int = 5, max_overflow: int = 5) -> AsyncEngine:
    """An engine whose pool holds `pool_size` connections, plus `max_overflow`
    more under load. The pool is per process: every uvicorn worker opens its own,
    so a deployment's connection budget is workers x (pool_size + max_overflow)
    (infra/STAGING.md).

    Newest connection first (LIFO), so a quiet pool keeps reusing the one it
    just used, warm and unchecked, and the rest can idle out; checked only after
    `CHECK_IF_IDLE_FOR` idle (P-53).
    """
    engine = create_async_engine(
        url, pool_size=pool_size, max_overflow=max_overflow, pool_use_lifo=True
    )
    event.listen(engine.sync_engine.pool, "checkin", _note_checkin)
    event.listen(engine.sync_engine.pool, "checkout", _check_if_idle)
    return engine


def _note_checkin(dbapi_connection: Any, record: ConnectionPoolEntry) -> None:
    record.info[_CHECKED_IN_AT] = clock.now()


def _check_if_idle(
    dbapi_connection: Any, record: ConnectionPoolEntry, proxy: PoolProxiedConnection
) -> None:
    """Check a connection idle for `CHECK_IF_IDLE_FOR`; a new one never is.

    A failed check raises DisconnectionError, on which the pool drops the
    connection and hands out a new one: the request never sees the dead one.
    """
    checked_in_at = record.info.get(_CHECKED_IN_AT)
    if checked_in_at is None or clock.now() - checked_in_at < CHECK_IF_IDLE_FOR:
        return
    try:
        dbapi_connection.ping()
    except Exception as error:  # whatever the failure, the connection is unusable
        raise exc.DisconnectionError(
            "an idle connection failed its liveness check"
        ) from error


class RequestSession(Session):
    """A request's session: one pooled connection, checked out at its first
    query and kept until the session closes (P-52).

    A session bound to the engine hands its connection back to the pool at the
    end of every transaction, and its next transaction checks out again,
    paying the pool's liveness check again. `current_user` ends a transaction
    of its own before the route's service begins another (T-3.5), so every
    authenticated request checked out twice. Bound to a connection, a session
    keeps it across transactions and leaves it open; this one opens it at first
    use, so a request that never reaches the database (a bad token) takes
    nothing from the pool, and closes it with the session.

    The connection is opened inside `get_bind`, which SQLAlchemy calls on the
    async session's greenlet. Calling `AsyncSession.get_bind()` from async code
    would run it off that greenlet: nothing does, and nothing should.
    """

    _request_connection: Connection | None = None

    def get_bind(self, mapper: Any = None, **kw: Any) -> Engine | Connection:
        bind = super().get_bind(mapper, **kw)
        if isinstance(bind, Connection):
            return bind
        if self._request_connection is None:
            self._request_connection = bind.connect()
        return self._request_connection

    # Every way a session ends hands the connection back.
    def close(self) -> None:
        try:
            super().close()
        finally:
            self._release_connection()

    def reset(self) -> None:
        try:
            super().reset()
        finally:
            self._release_connection()

    def invalidate(self) -> None:
        try:
            super().invalidate()
        finally:
            self._release_connection()

    def _release_connection(self) -> None:
        held, self._request_connection = self._request_connection, None
        if held is not None:
            held.close()


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Sessions for requests: each holds one connection while it lives (P-52)."""
    return async_sessionmaker(
        engine, expire_on_commit=False, sync_session_class=RequestSession
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, on this app's database.

    When the request ends, the events its committed transactions queued are
    published, after the session has closed and handed its connection back
    (`core/events.py`)."""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    committed: list[events.Event] = []
    try:
        async with sessionmaker() as session:
            try:
                yield session
            finally:
                committed = events.take_committed(session)
    finally:
        await events.publish(committed, request.app.state.redis)


async def check_database(engine: AsyncEngine) -> None:
    """Raise if Postgres cannot answer `SELECT 1`. Used only by `/readyz`."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
