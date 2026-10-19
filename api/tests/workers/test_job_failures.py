"""A job that has failed for good reaches Sentry (T-9.12): ARQ logs it through
the stdlib, and `ReportJobFailures` makes it `job.failed` at error level.
Run on a real ARQ worker: a job that raised, one that timed out, and one
picked up past its tries."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from typing import Any

import pytest
from arq import Retry, func
from arq.constants import (
    default_queue_name,
    in_progress_key_prefix,
    job_key_prefix,
    result_key_prefix,
    retry_key_prefix,
)
from arq.worker import Worker
from redis.asyncio import Redis

from app.core.queue import ArqQueue
from app.workers import main as worker
from tests.conftest import CapturedLogs, make_test_settings
from tests.sentry_capture import SentryEvents, worker_sentry_events

__all__ = ["worker_sentry_events"]  # the fixture, for this module's tests

PHONE = "+919812345678"


@pytest.fixture
async def queue(test_redis: Redis) -> AsyncIterator[Redis]:
    async def clear() -> None:
        await test_redis.delete(default_queue_name)
        for prefix in (
            job_key_prefix,
            result_key_prefix,
            retry_key_prefix,
            in_progress_key_prefix,
        ):
            async for key in test_redis.scan_iter(match=f"{prefix}*"):
                await test_redis.delete(key)

    await clear()
    try:
        yield test_redis
    finally:
        await clear()


async def crash(ctx: dict[Any, Any], *args: Any, **kwargs: Any) -> None:
    raise ValueError(f"no such user {PHONE}")


async def slow(ctx: dict[Any, Any], *args: Any, **kwargs: Any) -> None:
    await asyncio.sleep(5)


async def retrying(ctx: dict[Any, Any], *args: Any, **kwargs: Any) -> None:
    raise Retry(defer=0)


async def fine(ctx: dict[Any, Any], *args: Any, **kwargs: Any) -> str:
    return "done"


async def _run(queue: Redis) -> Worker:
    settings = make_test_settings()
    jobs = ArqQueue(queue)
    for name in ("crash", "slow", "retrying", "fine"):
        await jobs.enqueue(name)
    burst = Worker(
        functions=[
            func(crash, name="crash"),
            func(slow, name="slow", timeout=0.05),
            func(retrying, name="retrying", max_tries=2),
            func(fine, name="fine"),
        ],
        redis_settings=worker.redis_settings(settings),
        burst=True,
        poll_delay=0.01,
        handle_signals=False,
    )
    try:
        await burst.main()
    finally:
        await burst.close()
    return burst


async def test_each_job_that_failed_for_good_is_one_error_by_name_and_class(
    queue: Redis, captured_logs: CapturedLogs
) -> None:
    arq_logger = logging.getLogger("arq.worker")
    filters = list(arq_logger.filters)
    worker.report_job_failures()
    worker.report_job_failures()  # once is enough: a second adds nothing
    try:
        ran = await _run(queue)
    finally:
        added = [f for f in arq_logger.filters if f not in filters]
        arq_logger.filters[:] = filters

    assert [type(f) for f in added] == [worker.ReportJobFailures]
    assert (ran.jobs_complete, ran.jobs_failed) == (1, 3)
    failed = sorted(
        (e["job"], e["error"], e["log_level"])
        for e in captured_logs.events
        if e.get("event") == "job.failed"
    )
    assert failed == [
        ("crash", "ValueError", "error"),
        ("retrying", "out of tries", "error"),
        ("slow", "TimeoutError", "error"),
    ]
    # The line names the error's class, never its message, which can carry a
    # row's values. The exception rides along for its stack only: Sentry drops
    # its message (D-1003; the next test), and the container's log has ARQ's own line.
    fields = "\n".join(
        json.dumps({k: v for k, v in e.items() if k != "exc_info"}, default=str)
        for e in captured_logs.events
        if e.get("event") == "job.failed"
    )
    assert PHONE not in fields


def _failed_record() -> logging.LogRecord:
    """ARQ's line for a job that raised, as `run_job` writes it."""
    try:
        raise ValueError(f"no such user {PHONE}")
    except ValueError as error:
        return logging.LogRecord(
            "arq.worker",
            logging.ERROR,
            __file__,
            1,
            "%6.2fs ! %s failed, %s: %s",
            (0.01, "abc123:crash", "ValueError", error),
            sys.exc_info(),
        )


def test_a_failed_job_reaches_sentry_as_the_workers_with_its_stack(
    worker_sentry_events: SentryEvents,
) -> None:
    assert worker.ReportJobFailures().filter(_failed_record())

    (event,) = worker_sentry_events
    assert event["tags"]["component"] == "worker"
    assert event["tags"]["event"] == "job.failed"
    assert event["contexts"]["log"]["job"] == "crash"
    assert event["contexts"]["log"]["job_id"] == "abc123"
    (exception,) = event["exception"]["values"]
    assert (exception["type"], exception["value"]) == ("ValueError", "")
    assert PHONE not in worker_sentry_events.text()


def test_arqs_own_lines_are_the_ones_matched() -> None:
    """The two templates, read from the installed arq: an upgrade that changes
    either would leave job failures silent, so it fails here instead."""
    import inspect

    from arq import worker as arq_worker

    source = inspect.getsource(arq_worker)
    assert f"'{worker._JOB_FAILED}'" in source
    assert f"'{worker._JOB_OUT_OF_TRIES}'" in source


def test_any_other_arq_line_is_left_alone(captured_logs: CapturedLogs) -> None:
    record = logging.LogRecord(
        "arq.worker",
        logging.INFO,
        __file__,
        1,
        "%6.2fs ↻ %s retrying job in %0.2fs",
        (0.01, "abc123:retrying", 0.0),
        None,
    )

    assert worker.ReportJobFailures().filter(record)
    assert not [e for e in captured_logs.events if e.get("event") == "job.failed"]
