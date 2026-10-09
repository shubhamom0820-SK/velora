"""The Thread's clock (T-7.6): `expire_threads` and `warn_expiring`, run once
a minute by the worker's own loop (`app/workers/minutely.py`, D-640), never by
an ARQ cron, whose minute-by-minute jobs would cost Upstash's Free plan more
than it has (D-091).

- `expire_threads`: active Threads past `expires_at` → `expired`, and
  `thread.expired` to him (D-560: the status only catches the clock up; every
  check already reads expiry from the clock).
- `warn_expiring`: active Threads with `thread_warn_minutes` or less left, not
  yet warned for this expiry → warned, `thread.expiring` and a notification to
  him (T-7.6's answer 2).

Neither reaches her (D-097, D-554). Each works in batches of
`threads_service.SWEEP_BATCH`, one transaction each, until a batch comes back
short, and publishes a batch's events once it has committed, never under its
locks (`core/events.py`). A Thread another transaction holds is skipped and
taken the next minute. So a run is safe to repeat and to run on two workers at
once, and a failed one is the next minute's to finish.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.db import SessionOpener
from app.modules.threads import service as threads_service

Batch = Callable[[AsyncSession], Awaitable[int]]


async def _sweep(
    sessionmaker: SessionOpener,
    redis: Redis,
    batch: Batch,
    limit: int,
) -> int:
    total = 0
    while True:
        async with sessionmaker() as session:
            taken = await batch(session)
            committed = events.take_committed(session)
        await events.publish(committed, redis)
        total += taken
        if taken < limit:
            return total


async def expire_threads(
    sessionmaker: SessionOpener,
    redis: Redis,
    *,
    limit: int = threads_service.SWEEP_BATCH,
) -> int:
    """Every Thread due to expire, expired. How many."""

    async def batch(session: AsyncSession) -> int:
        return await threads_service.expire_batch(session, limit=limit)

    return await _sweep(sessionmaker, redis, batch, limit)


async def warn_expiring(
    sessionmaker: SessionOpener,
    redis: Redis,
    *,
    limit: int = threads_service.SWEEP_BATCH,
) -> int:
    """Every Thread due its warning, warned. How many."""

    async def batch(session: AsyncSession) -> int:
        return await threads_service.warn_batch(session, limit=limit)

    return await _sweep(sessionmaker, redis, batch, limit)


async def run(ctx: Mapping[str, Any]) -> dict[str, int]:
    """One minute's work, from the worker's context: expire first, so a Thread
    past its hour is never warned. How many of each."""
    expired = await expire_threads(ctx["sessionmaker"], ctx["redis"])
    warned = await warn_expiring(ctx["sessionmaker"], ctx["redis"])
    return {"expired": expired, "warned": warned}
