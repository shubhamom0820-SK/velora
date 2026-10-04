"""The job queue (T-4.2): onto ARQ's queue in Redis, once per job id."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from arq.constants import default_queue_name, job_key_prefix
from redis.asyncio import Redis

from app.core.queue import ArqQueue, FakeQueue


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
