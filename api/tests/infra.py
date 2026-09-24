"""Test infrastructure: where the test database is, whether it is safe and
reachable, and the transaction every test runs inside.

Deliberately imports nothing from `app`: conftest calls this *before* it has made
the environment safe, and importing the app first would read settings early.
"""

from __future__ import annotations

import os
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlsplit

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora_test"
)

# Test-only; not app config, so it lives here and in 06-TESTING.md, not in §11.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
TEST_REDIS_URL = "redis://127.0.0.1:6379/1"


def ensure_test_database(url: str) -> None:
    """Refuse any database whose name does not end in `_test`.

    Tests create tables and write rows. Pointed at the dev database — by an
    exported `DATABASE_URL`, a typo, or a copied config — they would do it there.
    """
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database {name!r}: the test database's "
            "name must end in '_test'. Set TEST_DATABASE_URL to a test database."
        )


def _reachable(url: str) -> bool:
    parts = urlsplit(url)
    if parts.hostname is None or parts.port is None:
        return False
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=0.5):
            return True
    except OSError:
        return False


def in_ci() -> bool:
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false")


InfraDecision = Literal["run", "skip", "fail"]


def infra_policy(*, reachable: bool, ci: bool) -> InfraDecision:
    """Locally, tests that need Postgres/Redis skip when they are down. In CI a
    missing database is an error, never a quiet skip: the wallet concurrency and
    ledger tests are exactly the ones that must not silently not run."""
    if reachable:
        return "run"
    return "fail" if ci else "skip"


# A bare TCP connect, deliberately not the app's own checks: a bug in
# check_database() must fail its test, not skip it.
INFRA_UP = _reachable(TEST_DATABASE_URL) and _reachable(TEST_REDIS_URL)
INFRA_DOWN_REASON = "Postgres or Redis not reachable — start them with `make infra-up`"

requires_infra = pytest.mark.skipif(not INFRA_UP, reason=INFRA_DOWN_REASON)


@asynccontextmanager
async def transactional_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is always rolled back.

    `create_savepoint` means code under test can `commit()` or open
    `session.begin()` freely — that only ever touches a savepoint, and the outer
    transaction is discarded at the end. Postgres rolls back DDL too, so even
    tables a test creates disappear.
    """
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            if outer.is_active:
                await outer.rollback()


class ActiveSession:
    """The current test's session, for the app's `get_session` override.

    A plain holder rather than a ContextVar: fixtures and the test body run in
    different tasks, so a ContextVar set in `db` would not be seen by requests.
    """

    session: AsyncSession | None = None


async def session_for_the_app() -> AsyncIterator[AsyncSession]:
    """Stands in for `get_session` in tests: the `db` fixture's session, or a
    loud refusal — a test that forgets `db` must not write for real."""
    if ActiveSession.session is None:
        raise RuntimeError(
            "This test reached the database without the `db` fixture. Request "
            "`db` so its writes are rolled back."
        )
    yield ActiveSession.session
