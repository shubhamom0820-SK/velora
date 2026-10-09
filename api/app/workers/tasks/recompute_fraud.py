"""`recompute_fraud` (T-9.2, D-031, D-900): every 10 minutes, in the worker's
own loop (`app/workers/minutely.py`), never an ARQ cron, which would cost
Upstash's Free plan about 86,000 commands a month (D-091); this costs none but
the `socket.close` a freeze publishes.

Whoever has a signal in the last 7 days, or a score still to decay, is scored
again (`safety.scoring.recompute`), each in a transaction of their own. A
person another transaction holds (a report being filed about them, another
worker) is skipped and taken next time: the report scores them itself. So a run
is safe to repeat and to run on two workers at once.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final
from uuid import UUID

from redis.asyncio import Redis

from app.core import clock, events
from app.core.db import SessionOpener
from app.modules.safety import fraud, repository, scoring

EVERY_S: Final = 600.0
BATCH: Final = 200


async def recompute_all(
    sessionmaker: SessionOpener, redis: Redis, *, batch: int = BATCH
) -> dict[str, int]:
    """Everyone due, scored. How many were, and how many that froze."""
    since = clock.now() - fraud.DECAY
    scored = frozen = 0
    after: UUID | None = None
    while True:
        async with sessionmaker() as session, session.begin():
            due = await repository.due_for_scoring(
                session, since, after=after, limit=batch
            )
        for user_id in due:
            async with sessionmaker() as session:
                async with session.begin():
                    outcome = await scoring.recompute(
                        session, user_id, skip_locked=True
                    )
                committed = events.take_committed(session)
            await events.publish(committed, redis)
            if outcome is not None:
                scored += 1
                frozen += outcome.frozen
        if len(due) < batch:
            return {"scored": scored, "frozen": frozen}
        after = due[-1]


async def run(ctx: Mapping[str, Any]) -> dict[str, int]:
    return await recompute_all(ctx["sessionmaker"], ctx["redis"])
