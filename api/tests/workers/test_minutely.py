"""The worker's minute (D-640, T-7.6): `Minutely` runs its work now and then a
minute apart, start to start; a failed minute is logged and the next one
runs; and the worker starts it beside the wake listener and stops it at
shutdown, running the Thread's clock."""

from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from typing import Any

import pytest

from app.workers import main as worker
from app.workers.minutely import EVERY_S, FAILING_AFTER, Minutely
from app.workers.tasks import thread_clock
from tests.conftest import CapturedLogs


class Stop(Exception):
    """Ends a loop under test after so many sleeps."""


def _sleeps(after: int) -> tuple[list[float], Any]:
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        if len(slept) >= after:
            raise Stop

    return slept, sleep


def test_it_runs_once_a_minute() -> None:
    assert EVERY_S == 60.0


async def test_runs_start_a_minute_apart_whatever_each_took() -> None:
    times = iter([0.0, 2.5, 60.0, 60.5])
    ran: list[int] = []

    async def work() -> dict[str, int]:
        ran.append(1)
        return {"done": 0}

    slept, sleep = _sleeps(after=2)
    loop = Minutely(work, name="test", sleep=sleep, monotonic=lambda: next(times))

    with pytest.raises(Stop):
        await loop.run()

    assert len(ran) == 2
    assert slept == [57.5, 59.5]


async def test_a_failed_minute_is_logged_and_the_next_one_runs(
    captured_logs: CapturedLogs,
) -> None:
    calls = 0

    async def work() -> dict[str, int]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("database at 10.0.0.1 went away")
        return {"expired": 3}

    _, sleep = _sleeps(after=2)
    loop = Minutely(work, name="thread_clock", sleep=sleep)

    with pytest.raises(Stop):
        await loop.run()

    assert (calls, loop.runs) == (2, 2)
    failed = [
        {key: each.get(key) for key in ("work", "error")}
        for each in captured_logs.events
        if each.get("event") == "minutely.failed"
    ]
    assert failed == [{"work": "thread_clock", "error": "ConnectionError"}]
    # The error's class only: its text can carry an address.
    assert "10.0.0.1" not in captured_logs.text
    ran = [e for e in captured_logs.events if e.get("event") == "minutely.ran"]
    assert [e.get("expired") for e in ran] == [3]


def test_the_third_failure_in_a_row_is_an_alert() -> None:
    """T-9.12's "any job failing 3×", for the loops ARQ doesn't run."""
    assert FAILING_AFTER == 3


async def test_three_failures_in_a_row_log_one_error_and_the_recovery_says_so(
    captured_logs: CapturedLogs,
) -> None:
    """Fail, fail, fail, fail, work, fail, fail, fail: an error at the third of
    each streak only, so a loop down all day is one alert, not 1,440."""
    script = iter([False, False, False, False, True, False, False, False])

    async def work() -> dict[str, int]:
        if not next(script):
            raise ConnectionError("database at 10.0.0.1 went away")
        return {}

    _, sleep = _sleeps(after=8)
    loop = Minutely(work, name="thread_clock", sleep=sleep)

    with pytest.raises(Stop):
        await loop.run()

    lines = [
        (each["event"], each.get("log_level"), each.get("failures"))
        for each in captured_logs.events
        if each.get("event") in ("minutely.failing", "minutely.recovered")
    ]
    assert lines == [
        ("minutely.failing", "error", 3),
        ("minutely.recovered", "info", 4),
        ("minutely.failing", "error", 3),
    ]
    failing = [e for e in captured_logs.events if e["event"] == "minutely.failing"]
    assert {(e["work"], e["error"]) for e in failing} == {
        ("thread_clock", "ConnectionError")
    }
    assert "10.0.0.1" not in captured_logs.text
    assert loop.failures_in_a_row == 3


async def test_a_streak_shorter_than_three_is_no_alert(
    captured_logs: CapturedLogs,
) -> None:
    script = iter([False, False, True, False, False, True])

    async def work() -> dict[str, int]:
        if not next(script):
            raise ConnectionError
        return {}

    _, sleep = _sleeps(after=6)

    with pytest.raises(Stop):
        await Minutely(work, name="thread_clock", sleep=sleep).run()

    assert not [
        e
        for e in captured_logs.events
        if e.get("event") in ("minutely.failing", "minutely.recovered")
    ]


async def test_an_idle_minute_writes_no_line(captured_logs: CapturedLogs) -> None:
    async def work() -> dict[str, int]:
        return {"expired": 0, "warned": 0}

    _, sleep = _sleeps(after=1)

    with pytest.raises(Stop):
        await Minutely(work, name="thread_clock", sleep=sleep).run()

    assert not [e for e in captured_logs.events if e.get("event") == "minutely.ran"]


async def test_cancelling_it_stops_it() -> None:
    async def work() -> dict[str, int]:
        return {}

    task = asyncio.create_task(Minutely(work, name="test").run())
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_the_worker_starts_the_threads_clock_and_stops_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`startup` starts the minute beside the wake listener, running
    `thread_clock.run` on its own context; `shutdown` cancels it."""
    ran = asyncio.Event()
    seen: list[MutableMapping[str, Any]] = []

    async def clock_run(ctx: MutableMapping[str, Any]) -> dict[str, int]:
        seen.append(ctx)
        ran.set()
        return {"expired": 0, "warned": 0}

    class Idle:
        async def run(self) -> None:
            await asyncio.Event().wait()

    async def no_resources(*_: Any) -> None:
        return None

    monkeypatch.setattr(thread_clock, "run", clock_run)
    monkeypatch.setattr(worker, "open_resources", no_resources)
    monkeypatch.setattr(worker, "build_providers", lambda _: None)
    monkeypatch.setattr(worker, "listen_for_wakes", lambda *_: Idle())
    ctx: dict[str, Any] = {}

    await worker.startup(ctx)
    try:
        async with asyncio.timeout(5):
            await ran.wait()
    finally:
        await worker.shutdown(ctx)

    assert seen == [ctx]
    assert ctx["minutely"].cancelled()
    assert ctx["wake"].cancelled()
