"""Events (`core/events.py`, T-5.1): kept on commit, dropped on rollback, and
published by `get_session` when the request ends, never before.

The first half drives a session directly. The second runs the app as
production builds it, with its own `get_session` and pool, so its rows are
committed for real: on fresh men, never deleted (tests/committed.py).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import events
from app.core.db import get_session
from app.core.providers import FakeProviders
from app.main import close_resources, create_app
from app.modules.wallet.models import Wallet
from tests.committed import fresh_man
from tests.conftest import CapturedLogs, make_test_settings
from tests.grants import grant

USER = uuid.uuid4()


def _queue(session: AsyncSession, balance: int) -> None:
    events.queue(session, USER, "wallet.updated", {"balance": balance})


def _balances(committed: list[events.Event]) -> list[int]:
    return [each.data["balance"] for each in committed]


# --- Kept on commit, dropped on rollback ---------------------------------------------


async def test_an_event_is_kept_when_its_transaction_commits(db: AsyncSession) -> None:
    await db.execute(text("select 1"))
    _queue(db, 1)
    assert events.take_committed(db) == []  # not before the commit

    await db.commit()

    assert events.take_committed(db) == [
        events.Event(USER, "wallet.updated", {"balance": 1})
    ]
    assert events.take_committed(db) == []  # handed over once


async def test_an_event_is_dropped_when_its_transaction_rolls_back(
    db: AsyncSession,
) -> None:
    await db.execute(text("select 1"))
    _queue(db, 1)

    await db.rollback()
    await db.execute(text("select 1"))
    await db.commit()

    assert events.take_committed(db) == []


async def test_a_rolled_back_savepoint_drops_only_its_own_events(
    db: AsyncSession,
) -> None:
    await db.execute(text("select 1"))
    _queue(db, 1)
    savepoint = await db.begin_nested()
    _queue(db, 2)
    await savepoint.rollback()
    _queue(db, 3)

    await db.commit()

    assert _balances(events.take_committed(db)) == [1, 3]


async def test_a_released_savepoints_events_wait_for_the_outer_commit(
    db: AsyncSession,
) -> None:
    await db.execute(text("select 1"))
    async with db.begin_nested():
        _queue(db, 1)
    assert events.take_committed(db) == []  # a release is not a commit

    await db.rollback()

    assert events.take_committed(db) == []


async def test_a_session_closed_mid_transaction_keeps_nothing(
    test_engine: AsyncEngine,
) -> None:
    session = AsyncSession(test_engine)
    await session.execute(text("select 1"))
    _queue(session, 1)

    await session.close()

    assert events.take_committed(session) == []


async def test_an_event_is_queued_only_inside_a_transaction(
    test_engine: AsyncEngine,
) -> None:
    async with AsyncSession(test_engine) as session:
        with pytest.raises(RuntimeError, match="inside the transaction that makes it"):
            _queue(session, 1)


# --- Published when the request ends -------------------------------------------------


@pytest.fixture
async def real_app(test_redis: Redis) -> AsyncIterator[FastAPI]:
    """The app with its own `get_session`, and a route that credits a man in a
    transaction of its own, then fails if told to."""
    application = create_app(make_test_settings())
    application.state.providers = FakeProviders().as_providers()

    @application.post("/v1/_test/credit")
    async def _credit(
        session: Annotated[AsyncSession, Depends(get_session)],
        user_id: uuid.UUID,
        amount: int,
        fail: bool = False,
    ) -> dict[str, bool]:
        async with session.begin():
            await grant(session, user_id, amount, event=f"events-test-{uuid.uuid4()}")
            if fail:
                raise RuntimeError("rolled back on purpose")
        return {"ok": True}

    try:
        yield application
    finally:
        await close_resources(application)


async def _credit(
    app: FastAPI, man: uuid.UUID, amount: int, *, fail: bool = False
) -> Response:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/v1/_test/credit",
            params={"user_id": str(man), "amount": amount, "fail": fail},
        )


@pytest.fixture
async def listening(test_redis: Redis) -> AsyncIterator[Any]:
    """A subscription, made per test: `await listening(man)` subscribes to the
    man's channel and returns a function that reads its next message."""
    pubsub = test_redis.pubsub()

    async def subscribe(man: uuid.UUID) -> Any:
        await pubsub.subscribe(f"user:{man}")
        # Redis's confirmation: from here, anything published reaches us.
        confirmed = await pubsub.get_message(timeout=2.0)
        assert confirmed is not None and confirmed["type"] == "subscribe"

        async def next_message(timeout: float = 2.0) -> dict[str, Any] | None:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=timeout
            )
            return None if message is None else json.loads(message["data"])

        return next_message

    try:
        yield subscribe
    finally:
        await pubsub.aclose()  # type: ignore[no-untyped-call]


async def test_a_committed_credit_is_published_when_the_request_ends(
    real_app: FastAPI, test_engine: AsyncEngine, listening: Any
) -> None:
    man = await fresh_man(test_engine)
    next_message = await listening(man)

    response = await _credit(real_app, man, 5)

    assert response.status_code == 200
    envelope = await next_message()
    assert envelope is not None
    assert set(envelope) == {"type", "id", "data"}
    assert (envelope["type"], envelope["data"]) == ("wallet.updated", {"balance": 5})
    assert uuid.UUID(envelope["id"])
    assert await next_message(timeout=0.2) is None


async def test_a_rolled_back_credit_publishes_nothing(
    real_app: FastAPI, test_engine: AsyncEngine, listening: Any
) -> None:
    """The first message to arrive is the committed request's, after it: so
    the subscription was listening when the rolled-back one ended."""
    man = await fresh_man(test_engine)
    next_message = await listening(man)

    failed = await _credit(real_app, man, 5, fail=True)
    committed = await _credit(real_app, man, 7)

    assert (failed.status_code, committed.status_code) == (500, 200)
    first = await next_message()
    assert first is not None and first["data"] == {"balance": 7}
    assert await next_message(timeout=0.2) is None


class _Redis:
    """Stands in for the app's Redis at publish time."""

    def __init__(self, publish: Any) -> None:
        self.publish = publish


async def test_a_failed_publish_is_logged_and_the_request_stands(
    real_app: FastAPI, test_engine: AsyncEngine, captured_logs: CapturedLogs
) -> None:
    man = await fresh_man(test_engine)

    async def refuse(channel: str, message: str) -> int:
        raise ConnectionError("Error connecting to redis://default:hunter2@cache:6379")

    real_redis, real_app.state.redis = real_app.state.redis, _Redis(refuse)
    try:
        response = await _credit(real_app, man, 5)
    finally:
        real_app.state.redis = real_redis

    assert response.status_code == 200
    assert await _balance(test_engine, man) == 5
    failures = [
        e for e in captured_logs.events if e["event"] == "events.publish_failed"
    ]
    assert [(f["error"], f["events"], f["types"]) for f in failures] == [
        ("ConnectionError", 1, ["wallet.updated"])
    ]
    assert "hunter2" not in captured_logs.text  # rule 15: no address, no password
    captured_logs.assert_listening()


async def test_a_publish_that_never_answers_is_cut_off(
    real_app: FastAPI,
    test_engine: AsyncEngine,
    captured_logs: CapturedLogs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Redis that takes the connection and never answers would otherwise
    hold every money request open at its end."""
    man = await fresh_man(test_engine)
    monkeypatch.setattr(events, "PUBLISH_TIMEOUT_S", 0.2)

    async def never_answer(channel: str, message: str) -> int:
        await asyncio.Event().wait()
        return 0

    real_redis, real_app.state.redis = real_app.state.redis, _Redis(never_answer)
    try:
        response = await asyncio.wait_for(_credit(real_app, man, 5), timeout=5)
    finally:
        real_app.state.redis = real_redis

    assert response.status_code == 200
    failures = [
        e for e in captured_logs.events if e["event"] == "events.publish_failed"
    ]
    assert [f["error"] for f in failures] == ["TimeoutError"]
    captured_logs.assert_listening()


async def test_the_publish_waits_for_the_session_to_close(
    real_app: FastAPI, test_engine: AsyncEngine
) -> None:
    """Nothing external while a connection is held, let alone a lock: when the
    publish runs, the request's connection is back in the pool."""
    man = await fresh_man(test_engine)
    pool = real_app.state.engine.sync_engine.pool
    held_at_publish: list[int] = []

    async def note_the_pool(channel: str, message: str) -> int:
        held_at_publish.append(pool.checkedout())
        return 1

    real_redis, real_app.state.redis = real_app.state.redis, _Redis(note_the_pool)
    try:
        response = await _credit(real_app, man, 5)
    finally:
        real_app.state.redis = real_redis

    assert response.status_code == 200
    assert held_at_publish == [0]


async def _balance(engine: AsyncEngine, man: uuid.UUID) -> int | None:
    async with AsyncSession(engine) as session:
        balance: int | None = await session.scalar(
            select(Wallet.balance).where(Wallet.user_id == man)
        )
        return balance
