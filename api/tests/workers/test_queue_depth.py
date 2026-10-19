"""The queue's depth, every 5 minutes (T-9.12, D-1004): past 1,000 jobs
waiting it is an error, once as it crosses, on the real queue in this run's
Redis; and the worker starts the loop and stops it."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, MutableMapping
from typing import Any

import pytest
from redis.asyncio import Redis

from app.workers import main as worker
from app.workers.minutely import Minutely
from app.workers.tasks import queue_depth, recompute_fraud, send_push, thread_clock
from app.workers.tasks.queue_depth import QueueDepth
from tests.conftest import CapturedLogs

# A queue of the test's own, so nothing a burst worker reads is touched.
QUEUE = "arq:queue:test-depth"


@pytest.fixture
async def queue(test_redis: Redis) -> AsyncIterator[Redis]:
    await test_redis.delete(QUEUE)
    try:
        yield test_redis
    finally:
        await test_redis.delete(QUEUE)


async def _fill(redis: Redis, jobs: int) -> None:
    await redis.delete(QUEUE)
    if jobs:
        await redis.zadd(QUEUE, {f"job-{n}": n for n in range(jobs)})


def _lines(captured_logs: CapturedLogs) -> list[tuple[str, str, int]]:
    return [
        (e["event"], e["log_level"], e["depth"])
        for e in captured_logs.events
        if str(e.get("event", "")).startswith("queue.")
    ]


def test_the_plans_numbers() -> None:
    """Every 5 minutes (the founder, 16 October 2026) and more than 1,000."""
    assert queue_depth.EVERY_S == 300
    assert queue_depth.DEPTH_LIMIT == 1000


async def test_crossing_1000_is_one_error_and_coming_back_one_info(
    queue: Redis, captured_logs: CapturedLogs
) -> None:
    check = QueueDepth({"redis": queue}, queue=QUEUE)

    for jobs in (1000, 1001, 1500, 1000, 999, 1001):
        await _fill(queue, jobs)
        assert await check.run() == {}

    assert _lines(captured_logs) == [
        ("queue.depth_high", "error", 1001),
        ("queue.depth_normal", "info", 1000),
        ("queue.depth_high", "error", 1001),
    ]
    assert check.high is True


async def test_an_empty_queue_writes_nothing(
    queue: Redis, captured_logs: CapturedLogs
) -> None:
    check = QueueDepth({"redis": queue}, queue=QUEUE)

    await check.run()

    assert _lines(captured_logs) == []


async def test_it_reads_arqs_own_queue_by_default(queue: Redis) -> None:
    from arq.constants import default_queue_name

    assert QueueDepth({"redis": queue})._queue == default_queue_name


async def test_the_worker_starts_the_depth_loop_every_5_minutes_and_stops_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = asyncio.Event()
    seen: list[float] = []

    async def depth_run(self: QueueDepth) -> dict[str, int]:
        ran.set()
        return {}

    async def idle_run(_ctx: MutableMapping[str, Any]) -> dict[str, int]:
        return {}

    class Idle:
        async def run(self) -> None:
            await asyncio.Event().wait()

    async def no_resources(*_: Any) -> None:
        return None

    real_minutely = Minutely

    def minutely(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs.get("every_s", 60.0))
        return real_minutely(*args, **kwargs)

    monkeypatch.setattr(QueueDepth, "run", depth_run)
    monkeypatch.setattr(recompute_fraud, "run", idle_run)
    monkeypatch.setattr(thread_clock, "run", idle_run)
    monkeypatch.setattr(send_push, "run", idle_run)
    monkeypatch.setattr(worker, "Minutely", minutely)
    monkeypatch.setattr(worker, "open_resources", no_resources)
    monkeypatch.setattr(worker, "build_providers", lambda _: None)
    monkeypatch.setattr(worker, "listen_for_wakes", lambda *_: Idle())
    monkeypatch.setattr(worker, "listen_for_pushes", lambda *_: Idle())
    ctx: dict[str, Any] = {}

    await worker.startup(ctx)
    try:
        async with asyncio.timeout(5):
            await ran.wait()
    finally:
        await worker.shutdown(ctx)

    assert 300.0 in seen
    assert ctx["queue_depth"].cancelled()
