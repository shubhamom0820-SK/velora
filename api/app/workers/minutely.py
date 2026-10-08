"""The worker's minute (D-640, T-7.6): work run once a minute inside the
worker's own process, never as an ARQ cron.

An ARQ cron job costs Redis commands each time it runs: queued, started, run
and finished, about 20 by arq 0.28's source, so one every minute is about
864,000 a month, over Upstash's whole Free plan (500,000) before the worker's
idle 260,640 (D-091). This loop costs none: the work it runs coordinates in
Postgres (`FOR UPDATE SKIP LOCKED`), so two workers running it at once take
different rows, and only the events it publishes reach Redis, one PUBLISH each.

It is `asyncio.create_task`ed at the worker's startup, as the wake listener is
(`wake.py`), and cancelled at shutdown. A failed minute is logged at warning
level, its error's class only, and never stops the loop: the work is
idempotent, so the next minute finishes it. Runs start a minute apart, start to
start, whatever each one took.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Final

import structlog

log = structlog.get_logger(__name__)

EVERY_S: Final = 60.0

# What a minute did, by name: logged when any of it is above 0, so an idle
# minute writes nothing.
Work = Callable[[], Awaitable[dict[str, int]]]


class Minutely:
    """Runs `work` now and then every `every_s` seconds, until cancelled."""

    def __init__(
        self,
        work: Work,
        *,
        name: str,
        every_s: float = EVERY_S,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._work = work
        self._name = name
        self._every_s = every_s
        self._sleep = sleep
        self._monotonic = monotonic
        # How many runs have finished, failed ones included: for tests.
        self.runs = 0

    async def run(self) -> None:
        while True:
            started = self._monotonic()
            try:
                done = await self._work()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 — the next minute tries again
                log.warning(
                    "minutely.failed", work=self._name, error=type(error).__name__
                )
            else:
                if any(done.values()):
                    log.info("minutely.ran", work=self._name, **done)
            self.runs += 1
            took = self._monotonic() - started
            await self._sleep(max(0.0, self._every_s - took))
