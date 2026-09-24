"""Database engine, sessions, and the readiness check.

One async engine per process, created lazily from `DATABASE_URL` so that tests
and scripts that never start the app's lifespan still get a working engine.
The app's lifespan creates it eagerly on startup and disposes it on shutdown.

Transactions are opened in the service layer (`async with session.begin():`);
repositories receive a session and never commit (`02-ARCHITECTURE.md` §2).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """The process-wide engine, created on first use."""
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    """Close every pooled connection. Safe to call when no engine exists."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed afterwards."""
    get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session


async def check_database() -> None:
    """Raise if Postgres cannot answer `SELECT 1`. Used only by `/readyz`."""
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))
