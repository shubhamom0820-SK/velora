"""The test harness.

Every test that touches Postgres runs inside a transaction that is rolled back,
on this run's own test database, never anything else (P-55, `tests/infra.py`). The app under test is built from explicit
test settings and shares that transaction.

Every external service is its in-memory fake (`fake_providers`, D-028): the
`app` fixture installs them, so no test can reach a real provider.

`make_user` builds a signed-up user and the access token the app accepts for
them.

`--shuffle-seed N` runs the tests in an order shuffled by N (P-48), to prove no
test leans on another's leftovers. Opt-in: CI runs them in file order.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import random
import uuid
from collections.abc import AsyncIterator, Iterator, MutableMapping
from dataclasses import dataclass
from datetime import date, timedelta
from types import ModuleType
from typing import Any, Protocol

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command as alembic_command
from app.core.config import PUBLIC_TEST_KEYS
from tests.infra import (
    INFRA_DOWN_REASON,
    INFRA_UP,
    RUN_SLOT,
    TEST_DATABASE_URL,
    TEST_REDIS_URL,
    ActiveSession,
    ensure_test_database,
    in_ci,
    infra_policy,
    run_alembic,
    session_for_the_app,
    session_opener_for_the_app,
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
    # The repo's public test keys (D-060): valid here, refused outside local.
    **PUBLIC_TEST_KEYS,
    "CORS_ORIGINS": "http://127.0.0.1:3000",
}.items():
    os.environ.setdefault(_key, _value)

from redis.asyncio import Redis

from app.core import clock as core_clock
from app.core import events
from app.core.clock import today_ist
from app.core.config import Settings
from app.core.db import build_engine, get_session, session_opener
from app.core.enums import (
    Gender,
    LedgerReason,
    MessageKind,
    OnboardingStep,
    Role,
    Seeking,
    ThreadOrigin,
    ThreadStatus,
    UserStatus,
)
from app.core.providers import FakeProviders
from app.core.queue import FakeQueue
from app.core.ratelimit import KEY_PREFIX as RATE_LIMIT_KEY_PREFIX
from app.core.redis import build_redis
from app.core.security import make_access_token, normalize_phone
from app.main import close_resources, create_app
from app.modules.auth.firebase_store import KEY_PREFIX as FIREBASE_KEY_PREFIX
from app.modules.auth.otp_store import KEY_PREFIX as OTP_KEY_PREFIX
from app.modules.messages.models import Message
from app.modules.threads.models import Thread
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service


def pytest_configure(config: pytest.Config) -> None:
    if infra_policy(reachable=INFRA_UP, ci=in_ci()) == "fail":
        pytest.exit(
            "CI requires Postgres and Redis, and they are not reachable "
            f"({INFRA_DOWN_REASON}). Refusing to skip database tests in CI.",
            returncode=3,
        )


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Which slot this run holds (P-55), and the order it runs in, so a report
    says where and how it ran."""
    if RUN_SLOT is None:
        lines = [f"test slot: none ({INFRA_DOWN_REASON})"]
    else:
        database = make_url(TEST_DATABASE_URL).database
        slot = RUN_SLOT.number
        lines = [f"test slot {slot}: database {database}, Redis database {slot}"]
    seed = config.getoption("--shuffle-seed")
    lines.append(
        "order: file order" if seed is None else f"order: shuffled by seed {seed}"
    )
    return lines


# --- Shuffled order (P-48) ------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--shuffle-seed",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Run the tests in an order shuffled by seed N (P-48). A test that "
            "passes only in file order leans on something an earlier test left "
            "behind, such as a logger cached before its capture began."
        ),
    )


def shuffled[T](items: list[T], seed: int) -> list[T]:
    """`items` in the order seed `seed` gives: the same seed, the same order."""
    order = list(items)
    random.Random(seed).shuffle(order)
    return order


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    seed = config.getoption("--shuffle-seed")
    if seed is not None:
        items[:] = shuffled(items, seed)


def make_test_settings() -> Settings:
    """Explicit settings for the app under test — never read from `.env`."""
    return Settings(
        _env_file=None,
        ENV="local",
        DATABASE_URL=TEST_DATABASE_URL,
        REDIS_URL=TEST_REDIS_URL,
        CORS_ORIGINS=["http://127.0.0.1:3000"],
        **PUBLIC_TEST_KEYS,  # type: ignore[arg-type]
    )


# --- Database -----------------------------------------------------------------


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """One engine on this run's test database for the whole run.

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
        ActiveSession.published = []
        try:
            yield session
        finally:
            ActiveSession.session = None


# --- App and client -----------------------------------------------------------


@pytest.fixture(autouse=True)
async def take_back_committed_notifications() -> AsyncIterator[None]:
    """After each test, what the app told the fresh men it committed is
    deleted (T-9.4, `tests/committed.py`): committed rows are taken back."""
    from tests import committed

    committed.COMMITTED_THIS_TEST.clear()
    yield
    if committed.COMMITTED_THIS_TEST:
        engine = build_engine(TEST_DATABASE_URL)
        try:
            await committed.take_back_notifications(
                engine, list(committed.COMMITTED_THIS_TEST)
            )
        finally:
            await engine.dispose()
            committed.COMMITTED_THIS_TEST.clear()


@pytest.fixture
def fake_providers() -> FakeProviders:
    """Every external service as its fake, for a test to steer and inspect:
    `fake_providers.sms.last_code(phone)`, `fake_providers.moderation.next = "reject:nudity"`.
    Quiet: the fake SMS doesn't echo codes to the terminal in tests."""
    return FakeProviders()


@pytest.fixture
def published(db: AsyncSession) -> list[events.Event]:
    """Every event this test's requests published through `client`, in order
    (P-64): what `get_session` sends to Redis, kept to read."""
    return ActiveSession.published


@pytest.fixture
def fake_queue() -> FakeQueue:
    """The job queue as a recorder: `fake_queue.named("moderate_photo")` lists
    what a request queued. Nothing runs; a worker test runs a job directly."""
    return FakeQueue()


@pytest.fixture
async def app(
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> AsyncIterator[FastAPI]:
    """The app, built from test settings; requests share the test's `db`, and
    every provider is the test's fake, and the job queue `fake_queue`. What a
    request publishes reaches Redis, as in the app, and `published` (P-64)."""
    application = create_app(make_test_settings())
    application.dependency_overrides[get_session] = session_for_the_app
    application.dependency_overrides[session_opener] = session_opener_for_the_app
    application.state.providers = fake_providers.as_providers()
    application.state.queue = fake_queue
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


# --- Users --------------------------------------------------------------------


class MakeUser(Protocol):
    async def __call__(
        self,
        gender: Gender | str = Gender.MALE,
        *,
        onboarded: bool = True,
        credits: int = 0,
        verified: bool | None = None,
    ) -> tuple[User, str]: ...


_user_serial = itertools.count(1)


@pytest.fixture
def make_user(db: AsyncSession) -> MakeUser:
    """A user as signup and onboarding leave them, and an access token the `app`
    fixture accepts: `user, token = await make_user(gender="female")`.

    Signup's own service writes the four rows (users, profiles, wallets at 0,
    notification_prefs; T-3.3), so a test finds the user exactly as sign-in
    will. The token's `auth_time` is now: a fresh sign-in (D-071).

    - `onboarded=True`: step `done`, 25 or so, the profile filled in, seeking the
      other gender. No interests, intents or photos: their tasks extend this.
    - `onboarded=False`: step `seeking`, the one after gender; profile empty.
    - `verified` follows D-008 unless given: an onboarded woman is verified, and
      asking for one who isn't raises, since the app can't produce her.
    - `credits` are granted through `wallet.service.credit()`, an `admin_grant`
      under the event `make_user`, as anything is (rule 5); nothing writes a
      balance directly. Anyone but a man is refused by the wallet (D-076).
    """
    settings = make_test_settings()

    async def factory(
        gender: Gender | str = Gender.MALE,
        *,
        onboarded: bool = True,
        credits: int = 0,
        verified: bool | None = None,
    ) -> tuple[User, str]:
        gender = Gender(gender)
        woman_onboarded = onboarded and gender is Gender.FEMALE
        if verified is None:
            verified = woman_onboarded
        elif woman_onboarded and not verified:
            raise ValueError(
                "An onboarded woman is always verified (D-008): the app can't "
                "produce one who isn't, so tests mustn't either."
            )

        serial = next(_user_serial)
        phone = normalize_phone(f"+9198{serial:08d}")
        account = await users_service.create_account(db, phone, settings)
        user, profile = account.user, account.profile
        user.gender = gender
        user.dob = date(today_ist().year - 25, 1, 1)
        user.role = Role.USER
        user.status = UserStatus.ACTIVE
        user.onboarding_step = (
            OnboardingStep.DONE if onboarded else OnboardingStep.SEEKING
        )
        user.is_verified = verified
        if onboarded:
            profile.first_name = "Test"
            profile.username = f"user{serial}"
            profile.about = "A test profile, with an about long enough for the rules."
            profile.hometown = "Phagwara"
            profile.city = "Phagwara"
            profile.seeking = Seeking.WOMEN if gender is Gender.MALE else Seeking.MEN
        await db.flush()
        await db.refresh(user)
        if credits:
            # Each user's grant is its own transaction, as a real one is: the
            # wallet refuses a man locked below one the transaction already
            # holds (P-63). Commits here only release savepoints; the test's
            # transaction still rolls it all back. Then one is open again, as
            # the caller had it before.
            await db.commit()
            await db.connection()
            await wallet_service.credit(
                db, user.id, credits, LedgerReason.ADMIN_GRANT, event="make_user"
            )
            await db.commit()
            await db.connection()
        token = make_access_token(
            user.id, user.role, settings, auth_time=core_clock.now()
        )
        return user, token

    return factory


class MakeThread(Protocol):
    async def __call__(
        self,
        a: User,
        b: User,
        *,
        status: ThreadStatus | str = ThreadStatus.ACTIVE,
        origin: ThreadOrigin | str = ThreadOrigin.MATCH,
        messages: int = 0,
    ) -> Thread: ...


@pytest.fixture
def make_thread(db: AsyncSession) -> MakeThread:
    """A Thread between `a` and `b`, opened by `a`, as the rules leave one
    (06-TESTING's fixture): active from a match expires in 24 hours, active
    and private never does, expired ran out an hour ago, knotted has no
    expiry. `messages` text messages from `a`, counted on the Thread. Written
    directly, charging nothing: what opening costs is T-7.1's own tests'."""

    async def factory(
        a: User,
        b: User,
        *,
        status: ThreadStatus | str = ThreadStatus.ACTIVE,
        origin: ThreadOrigin | str = ThreadOrigin.MATCH,
        messages: int = 0,
    ) -> Thread:
        status, origin = ThreadStatus(status), ThreadOrigin(origin)
        now = core_clock.now()
        expires_at = {
            ThreadStatus.ACTIVE: None
            if origin is ThreadOrigin.DM
            else now + timedelta(hours=24),
            ThreadStatus.EXPIRED: now - timedelta(hours=1),
            ThreadStatus.KNOTTED: None,
        }[status]
        knotted = status is ThreadStatus.KNOTTED
        # Python orders UUIDs as Postgres does: by their bytes.
        low, high = sorted((a.id, b.id))
        thread = Thread(
            user_low=low,
            user_high=high,
            origin=origin,
            opened_by=a.id,
            status=status,
            expires_at=expires_at,
            knotted_at=now if knotted else None,
            low_knot_at=now if knotted else None,
            high_knot_at=now if knotted else None,
        )
        db.add(thread)
        await db.flush()
        for n in range(messages):
            db.add(
                Message(
                    thread_id=thread.id,
                    sender_id=a.id,
                    kind=MessageKind.TEXT,
                    body=f"Message {n + 1}",
                    client_msg_id=uuid.uuid4(),
                    # A second apart, the last at `now`: one test's rows share
                    # a transaction, so `now()` alone would tie them all.
                    created_at=now - timedelta(seconds=messages - 1 - n),
                )
            )
        if messages:
            thread.message_count = messages
            thread.last_message_at = now
        await db.flush()
        await db.refresh(thread)
        return thread

    return factory


# --- Redis --------------------------------------------------------------------


@pytest.fixture
async def test_redis() -> AsyncIterator[Redis]:
    """The test Redis, with no rate-limit windows, sign-in codes or spent
    Firebase tokens left over from another test.

    Rate limits outlive a request by design, so without this the sixth test to
    post from the same address in a minute would fail for a reason it never
    chose; a day's count of codes sent would run into the cap the same way.
    Cleared before and after.
    """
    if not INFRA_UP:
        pytest.skip(INFRA_DOWN_REASON)
    client = build_redis(TEST_REDIS_URL)

    async def clear() -> None:
        for prefix in (RATE_LIMIT_KEY_PREFIX, OTP_KEY_PREFIX, FIREBASE_KEY_PREFIX):
            async for key in client.scan_iter(match=f"{prefix}*"):
                await client.delete(key)

    await clear()
    try:
        yield client
    finally:
        await clear()
        await client.aclose()


# --- Time ---------------------------------------------------------------------


@pytest.fixture
def clock() -> Iterator[ModuleType]:
    """`core.clock`, to freeze and advance. Always unfrozen after the test."""
    from app.core import clock as clock_module

    try:
        yield clock_module
    finally:
        clock_module.unfreeze()


# --- Logs, for rule 15 ------------------------------------------------------------

PROBE = "rule15_probe"


@dataclass
class CapturedLogs:
    events: list[MutableMapping[str, Any]]
    caplog: pytest.LogCaptureFixture

    def _records(self) -> list[logging.LogRecord]:
        # The probe is logged while the fixture is set up: another phase.
        return [*self.caplog.get_records("setup"), *self.caplog.records]

    @property
    def text(self) -> str:
        """Every captured line, structlog's events and the stdlib's records."""
        lines = [json.dumps(dict(event), default=str) for event in self.events]
        lines += [record.getMessage() for record in self._records()]
        return "\n".join(lines)

    def assert_listening(self) -> None:
        """Both probes arrived: a check that found nothing secret proves
        something only if the capture was listening (P-48)."""
        assert any(e.get("event") == PROBE for e in self.events)
        assert any(r.getMessage() == PROBE for r in self._records())


@pytest.fixture
def captured_logs(caplog: pytest.LogCaptureFixture) -> Iterator[CapturedLogs]:
    """Every log line a test's code emits, structlog's and the stdlib's, with a
    probe logged through each at the start. End a rule-15 test with
    `captured_logs.assert_listening()` beside its "nothing secret" check."""
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as events:
        structlog.get_logger("rule15").info(PROBE)
        logging.getLogger("rule15").warning(PROBE)
        yield CapturedLogs(events, caplog)
