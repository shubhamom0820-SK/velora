"""The queue's depth, every 5 minutes (T-9.12, D-1004).

More than 1,000 jobs waiting means the worker isn't keeping up, or isn't
running: logged at error level, so it reaches Sentry, once as the depth crosses
the line, and at info as it comes back under. Run in the worker's own loop, the
minute's kind (`Minutely`), never an ARQ cron, which would cost about 20 Redis
commands a run.

**The cost:** one `ZCARD` a run, 8,640 commands a month at 5 minutes, about 1.7%
of Upstash Free's 500,000 (D-091 left about 239,000 for real traffic). Every
minute would be 43,200, 8.6%: 5 minutes was the founder's call (D-1004).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import structlog
from arq.constants import default_queue_name

log = structlog.get_logger(__name__)

EVERY_S: Final = 300.0
# Jobs waiting before it is an alert.
DEPTH_LIMIT: Final = 1_000


class QueueDepth:
    """Reads the queue's depth; alerts on crossing `DEPTH_LIMIT`, not on each
    reading above it, so a backlog is one alert, not one every 5 minutes."""

    def __init__(
        self, ctx: Mapping[str, Any], *, queue: str = default_queue_name
    ) -> None:
        # The worker's context, read at each run: ARQ's own Redis pool.
        self._ctx = ctx
        self._queue = queue
        self.high = False

    async def run(self) -> dict[str, int]:
        depth = int(await self._ctx["redis"].zcard(self._queue))
        if depth > DEPTH_LIMIT and not self.high:
            log.error("queue.depth_high", depth=depth, limit=DEPTH_LIMIT)
        elif depth <= DEPTH_LIMIT and self.high:
            log.info("queue.depth_normal", depth=depth, limit=DEPTH_LIMIT)
        self.high = depth > DEPTH_LIMIT
        # Nothing for the loop's own line: an idle check writes nothing.
        return {}
