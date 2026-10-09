"""A job's events reach the person's sockets (P-592): the worker's sessions
publish what their committed transactions queued once they close, as a
request's session does (`core/events.py`). Before, only `get_session`
published, so a reward credited in `verify_selfie` never moved a balance on
screen until a reload.

The first two run the worker's own context, `open_resources`, and write no
rows: an event needs a transaction, not a change. The third runs a real job,
in the `db` fixture's rolled-back transaction, since its ledger rows could
never be deleted (tests/committed.py)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.db import publishing
from app.core.enums import Gender
from app.core.providers import FakeProviders
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.workers import main as worker
from app.workers.tasks import verify_selfie as job
from tests.conftest import MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.referrals.support import REWARD, RUNNING, refer, set_config
from tests.modules.verification.support import at_selfie, face_photo, submitted


class _Failed(Exception):
    pass


@pytest.fixture
async def listening(test_redis: Redis) -> AsyncIterator[Any]:
    """`await listening(user)` subscribes to the user's channel and returns a
    function that reads every message published on it within `timeout`."""
    pubsub = test_redis.pubsub()

    async def subscribe(user_id: uuid.UUID) -> Any:
        await pubsub.subscribe(f"user:{user_id}")
        confirmed = await pubsub.get_message(timeout=2.0)
        assert confirmed is not None and confirmed["type"] == "subscribe"

        async def received(timeout: float = 1.0) -> list[dict[str, Any]]:
            found = []
            while (
                message := await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=timeout
                )
            ) is not None:
                found.append(
                    {
                        "channel": message["channel"].decode(),
                        **json.loads(message["data"]),
                    }
                )
            return found

        return received

    try:
        yield subscribe
    finally:
        await pubsub.aclose()  # type: ignore[no-untyped-call]


@pytest.fixture
async def worker_ctx(test_redis: Redis) -> AsyncIterator[dict[str, Any]]:
    """The worker's context as `startup` builds it, on the test settings."""
    ctx: dict[str, Any] = {"redis": test_redis}
    await worker.open_resources(
        ctx, make_test_settings(), FakeProviders().as_providers()
    )
    try:
        yield ctx
    finally:
        await worker.shutdown(ctx)


async def test_a_jobs_committed_event_reaches_the_persons_sockets(
    worker_ctx: dict[str, Any], listening: Any
) -> None:
    someone = uuid.uuid4()
    received = await listening(someone)

    async with worker_ctx["sessionmaker"]() as session, session.begin():
        events.queue(session, someone, "wallet.updated", {"balance": 7})

    [event] = await received()
    assert (event["channel"], event["type"], event["data"]) == (
        f"user:{someone}",
        "wallet.updated",
        {"balance": 7},
    )


async def test_a_jobs_rolled_back_event_is_never_published(
    worker_ctx: dict[str, Any], listening: Any
) -> None:
    someone = uuid.uuid4()
    received = await listening(someone)

    with pytest.raises(_Failed):
        async with worker_ctx["sessionmaker"]() as session, session.begin():
            events.queue(session, someone, "wallet.updated", {"balance": 7})
            raise _Failed

    assert await received(timeout=0.5) == []


async def test_a_reward_credited_in_verify_selfie_moves_both_balances(
    db: AsyncSession, make_user: MakeUser, test_redis: Redis, listening: Any
) -> None:
    """P-592's worst case: the referee's selfie matches in the job, both men
    are credited, and each hears `wallet.updated` with the new balance."""
    await set_config(db, REWARD, str(RUNNING))
    referrer, _ = await make_user()
    referee, _ = await at_selfie(db, make_user, Gender.MALE)
    await refer(db, referee, referrer)
    storage, facematch = FakeStorage(), FakeFaceMatch()
    await face_photo(db, storage, referee)
    verification, _ = await submitted(db, storage, referee)
    facematch.next = FaceMatch(model="fake", faces_in_selfie=1, similarities=(0.71,))
    heard = {man.id: await listening(man.id) for man in (referee, referrer)}
    ctx = {
        # The worker's wrapping, around the test's own rolled-back session.
        "sessionmaker": publishing(Sessions(db), test_redis),
        "storage": storage,
        "facematch": facematch,
        "queue": FakeQueue(),
        "settings": make_test_settings(),
        "job_try": 1,
    }

    assert await job.verify_selfie(ctx, verification_id=str(verification.id)) == (
        "approved"
    )

    # One subscription hears both channels: each man's balance on his own.
    received = await heard[referee.id]()
    balances = {
        event["channel"]: event["data"]["balance"]
        for event in received
        if event["type"] == "wallet.updated"
    }
    assert balances == {f"user:{referee.id}": RUNNING, f"user:{referrer.id}": RUNNING}
