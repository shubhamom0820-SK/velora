"""The job queue (T-4.2): onto ARQ's queue in Redis, once per job id."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from arq.constants import default_queue_name, job_key_prefix
from redis.asyncio import Redis

from app.core.queue import WAKE_TIMEOUT_S, ArqQueue, FakeQueue, wake_channel
from tests.conftest import CapturedLogs


@pytest.fixture
async def arq_redis(test_redis: Redis) -> AsyncIterator[Redis]:
    """This run's Redis (P-55), with ARQ's keys cleared before and after."""

    async def clear() -> None:
        await test_redis.delete(default_queue_name)
        async for key in test_redis.scan_iter(match=f"{job_key_prefix}*"):
            await test_redis.delete(key)

    await clear()
    try:
        yield test_redis
    finally:
        await clear()


async def test_a_job_lands_on_arqs_queue_once_per_id(arq_redis: Redis) -> None:
    queue = ArqQueue(arq_redis)

    await queue.enqueue("moderate_photo", job_id="moderate_photo:p1", photo_id="p1")
    await queue.enqueue("moderate_photo", job_id="moderate_photo:p1", photo_id="p1")

    assert await arq_redis.zrange(default_queue_name, 0, -1) == [b"moderate_photo:p1"]
    assert await arq_redis.exists(f"{job_key_prefix}moderate_photo:p1") == 1


async def test_a_deferred_job_is_scored_for_later(arq_redis: Redis) -> None:
    queue = ArqQueue(arq_redis)

    await queue.enqueue("delete_files", job_id="soon", defer_by=None)
    await queue.enqueue("delete_files", job_id="later", defer_by=timedelta(seconds=60))

    soon = await arq_redis.zscore(default_queue_name, "soon")
    later = await arq_redis.zscore(default_queue_name, "later")
    assert soon is not None and later is not None
    assert 59_000 <= later - soon <= 61_000  # milliseconds


async def test_the_fake_records_once_per_id_and_can_refuse() -> None:
    queue = FakeQueue()

    await queue.enqueue("moderate_photo", job_id="a", photo_id="1")
    await queue.enqueue("moderate_photo", job_id="a", photo_id="1")
    queue.fail = True
    with pytest.raises(ConnectionError):
        await queue.enqueue("moderate_photo", job_id="b", photo_id="2")

    assert [(q.job_id, q.kwargs) for q in queue.named("moderate_photo")] == [
        ("a", {"photo_id": "1"})
    ]


# --- Wakes (D-261, T-4.5) ------------------------------------------------------------


async def test_a_wake_is_published_on_the_jobs_own_channel(test_redis: Redis) -> None:
    """A job name of this test's own: Redis shares channels across databases,
    and a real `wake:verify_selfie` would reach any worker running here."""
    job = f"test-{uuid.uuid4()}"
    async with test_redis.pubsub() as pubsub:
        await pubsub.subscribe(wake_channel(job))
        await pubsub.get_message(timeout=1)  # the subscribe's own reply

        await ArqQueue(test_redis).wake(job, "a-verification-id")

        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
    assert message is not None
    assert (message["channel"], message["data"]) == (
        f"wake:{job}".encode(),
        b"a-verification-id",
    )


async def test_a_wake_that_fails_is_logged_and_never_raises(
    captured_logs: CapturedLogs,
) -> None:
    """The submit has committed by then, and its job is queued: a Redis that
    refuses, or never answers, costs the person 10 seconds, not the request."""
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    try:
        await ArqQueue(broken).wake("verify_selfie", "an-id")
    finally:
        await broken.aclose()

    [failed] = [e for e in captured_logs.events if e["event"] == "queue.wake_failed"]
    assert (failed["log_level"], failed["job"]) == ("warning", "verify_selfie")
    captured_logs.assert_listening()


async def test_a_wake_that_hangs_gives_up_after_a_second(
    monkeypatch: pytest.MonkeyPatch, captured_logs: CapturedLogs
) -> None:
    client = Redis.from_url("redis://127.0.0.1:1/0")
    queue = ArqQueue(client)

    async def never(*args: object) -> int:
        await asyncio.sleep(3600)
        return 0

    monkeypatch.setattr(queue._arq, "publish", never)
    started = asyncio.get_running_loop().time()

    try:
        await queue.wake("verify_selfie", "an-id")
    finally:
        await client.aclose()

    assert asyncio.get_running_loop().time() - started < WAKE_TIMEOUT_S + 0.5
    assert "queue.wake_failed" in captured_logs.text


async def test_the_fake_records_wakes() -> None:
    queue, seen = FakeQueue(), []
    queue.on_wake = lambda: seen.append(len(queue.woken))

    await queue.wake("verify_selfie", "v1")

    assert (queue.woken, seen) == ([("verify_selfie", "v1")], [0])
