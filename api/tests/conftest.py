"""The test harness.

Every test that touches Postgres runs inside a transaction that is rolled back,
on `velora_test`, never anything else. The app under test is built from explicit
test settings and shares that transaction.

Every external service is its in-memory fake (`fake_providers`, D-028): the
`app` fixture installs them, so no test can reach a real provider.

Still to come, with the task that builds what it needs: `make_user` (T-3.1).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from types import ModuleType

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command as alembic_command
from tests.infra import (
    INFRA_DOWN_REASON,
    INFRA_UP,
    TEST_DATABASE_URL,
    TEST_REDIS_URL,
    ActiveSession,
    ensure_test_database,
    in_ci,
    infra_policy,
    run_alembic,
    session_for_the_app,
    transactional_session,
)

# --- Make the environment safe before anything imports the app ---------------
#
# Overridden, not defaulted: a developer with the dev DATABASE_URL exported in
# their shell must still get tests on the test database.
ensure_test_database(TEST_DATABASE_URL)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
for _key, _value in {
    "ENV": "local",
    "JWT_SECRET": "test-secret-not-a-real-key",
    "PHONE_PEPPER": "test-pepper",
    "PHONE_ENC_KEY": "test-enc-key",
    "CORS_ORIGINS": "http://localhost:3000",
}.items():
    os.environ.setdefault(_key, _value)

from app.core.config import Settings
from app.core.db import build_engine, get_session
from app.core.providers import FakeProviders
from app.main import close_resources, create_app


def pytest_configure(config: pytest.Config) -> None:
    if infra_policy(reachable=INFRA_UP, ci=in_ci()) == "fail":
        pytest.exit(
            "CI requires Postgres and Redis, and they are not reachable "
            f"({INFRA_DOWN_REASON}). Refusing to skip database tests in CI.",
            returncode=3,
        )


def make_test_settings() -> Settings:
    """Explicit settings for the app under test — never read from `.env`."""
    return Settings(
        _env_file=None,
        ENV="local",
        DATABASE_URL=TEST_DATABASE_URL,
        REDIS_URL=TEST_REDIS_URL,
        JWT_SECRET="test-secret-not-a-real-key",
        PHONE_PEPPER="test-pepper",
        PHONE_ENC_KEY="test-enc-key",
        CORS_ORIGINS=["http://localhost:3000"],
    )


# --- Database -----------------------------------------------------------------


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """One engine on `velora_test` for the whole run.

    Migrated to head once, here; each test's writes are then rolled back.
    """
    if not INFRA_UP:
        pytest.skip(INFRA_DOWN_REASON)
    engine = build_engine(TEST_DATABASE_URL)
    await run_alembic(engine, alembic_command.upgrade, "head")
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose every write — commits included — is rolled back."""
    async with transactional_session(test_engine) as session:
        ActiveSession.session = session
        try:
            yield session
        finally:
            ActiveSession.session = None


# --- App and client -----------------------------------------------------------


@pytest.fixture
def fake_providers() -> FakeProviders:
    """Every external service as its fake, for a test to steer and inspect:
    `fake_providers.sms.last_code(phone)`, `fake_providers.moderation.next = "reject:nudity"`.
    Quiet: the fake SMS doesn't echo codes to the terminal in tests."""
    return FakeProviders()


@pytest.fixture
async def app(fake_providers: FakeProviders) -> AsyncIterator[FastAPI]:
    """The app, built from test settings; requests share the test's `db`, and
    every provider is the test's fake."""
    application = create_app(make_test_settings())
    application.dependency_overrides[get_session] = session_for_the_app
    application.state.providers = fake_providers.as_providers()
    try:
        yield application
    finally:
        # The in-process transport does not run the lifespan, so close here.
        await close_resources(application)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client bound to `app`, without going over the network."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Time ---------------------------------------------------------------------


@pytest.fixture
def clock() -> Iterator[ModuleType]:
    """`core.clock`, to freeze and advance. Always unfrozen after the test."""
    from app.core import clock as clock_module

    try:
        yield clock_module
    finally:
        clock_module.unfreeze()
