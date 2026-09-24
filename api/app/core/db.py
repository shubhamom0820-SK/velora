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

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


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
