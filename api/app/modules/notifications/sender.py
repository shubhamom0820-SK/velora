"""Sending what waits in `push_outbox` (T-9.4, D-850): the worker's side.

Run when the worker hears a wake on `wake:send_push` and once a minute in its
own loop (D-640), so a lost wake costs a minute, never the push. Each batch is
claimed in one short transaction (`FOR UPDATE SKIP LOCKED`, then `claimed_at`),
and sent after it has committed, with no row locked while a push service is
waiting on the network. Two senders at once take different rows; a sender that
dies mid-send leaves a claim that goes stale and is taken again.

At send time, again: the account is active, the kind's setting is on, there is
a subscription, and the push is under an hour old (`rules.PUSH_TTL_S`). A
message is pushed only while its recipient has no socket open on any API
instance (D-854): each instance subscribes `user:{id}` while one is open, so
Redis's `PUBSUB NUMSUB` counts them, one command. With `generic_text` on, no
name is sent.

A subscription the push service calls gone (404, 410) is deleted. A failure is
tried again, `rules.PUSH_ATTEMPTS` times in all, then dropped. Whatever
happens, the outbox row goes, and the in-app row it came with stays.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock, events
from app.core.providers.push import PushOutcome, PushProvider, PushSubscription, Urgency
from app.modules.notifications import repository, rules
from app.modules.notifications.rules import Kind

log = structlog.get_logger(__name__)

BATCH: Final = 50
# Shown at once on a locked phone; the rest can wait for the next check.
URGENT: Final = frozenset({Kind.MESSAGE, Kind.THREAD, Kind.MATCH})


async def connected(redis: Redis, user_id: UUID) -> bool:
    """Whether `user_id` has a socket open on any API instance. Redis failing
    counts as not: a push twice beats a message nobody is told of."""
    channel = events.user_channel(user_id)
    try:
        counts = await redis.pubsub_numsub(channel)
    except Exception as error:  # noqa: BLE001 — push rather than stay silent
        log.warning("push.presence_unknown", error=type(error).__name__)
        return False
    return any(count > 0 for _, count in counts)


async def send_waiting(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    push: PushProvider,
    *,
    limit: int = BATCH,
) -> dict[str, int]:
    """Every push waiting, sent or settled, batch by batch. What happened to
    them, by outcome."""
    totals: Counter[str] = Counter()
    while True:
        async with sessionmaker() as session, session.begin():
            now = clock.now()
            rows = await repository.claim(
                session, now, now - timedelta(seconds=rules.CLAIM_STALE_S), limit
            )
            claimed = [
                (
                    row.id,
                    row.user_id,
                    row.kind,
                    row.payload,
                    row.attempts,
                    row.created_at,
                )
                for row in rows
            ]
        for each in claimed:
            totals[await _send_one(sessionmaker, redis, push, *each)] += 1
        if len(claimed) < limit:
            if totals:
                log.info("push.drained", **totals)
            return dict(totals)


async def _send_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    push: PushProvider,
    outbox_id: UUID,
    user_id: UUID,
    kind_name: str,
    payload: dict[str, Any],
    attempts: int,
    created_at: datetime,
) -> str:
    try:
        kind = Kind(kind_name)
    except ValueError:
        log.warning("push.unknown_kind", kind=kind_name)
        return await _settle(sessionmaker, outbox_id, "unknown")
    age_s = (clock.now() - created_at).total_seconds()
    if age_s >= rules.PUSH_TTL_S:
        return await _settle(sessionmaker, outbox_id, "stale")
    named = _named(kind, payload)
    async with sessionmaker() as session, session.begin():
        context = await repository.push_context(
            session, user_id, rules.PREF_FOR[kind], named
        )
        subscriptions = await repository.subscriptions(session, user_id)
    if context is None:
        return await _settle(sessionmaker, outbox_id, "skipped")
    status, wanted, generic_text, name, blocked = context
    if not rules.told(status) or not wanted or not subscriptions or blocked:
        return await _settle(sessionmaker, outbox_id, "skipped")
    if kind in rules.ONLY_IF_NOT_CONNECTED and await connected(redis, user_id):
        return await _settle(sessionmaker, outbox_id, "connected")

    data = rules.push_data(kind, payload, None if generic_text else name)
    urgency: Urgency = "high" if kind in URGENT else "normal"
    ttl_s = max(1, int(rules.PUSH_TTL_S - age_s))
    outcomes: list[tuple[str, PushOutcome]] = []
    for endpoint, p256dh, auth in subscriptions:
        outcome = await push.send(
            PushSubscription(endpoint, p256dh, auth), data, ttl_s=ttl_s, urgency=urgency
        )
        outcomes.append((endpoint, outcome))

    retry = any(outcome == "retry" for _, outcome in outcomes)
    async with sessionmaker() as session, session.begin():
        now = clock.now()
        for endpoint, outcome in outcomes:
            if outcome == "gone":
                await repository.drop_gone(session, user_id, endpoint)
            elif outcome == "sent":
                await repository.mark_ok(session, user_id, endpoint, now)
        if retry and attempts < rules.PUSH_ATTEMPTS:
            await repository.release(session, outbox_id)
        else:
            await repository.finish(session, outbox_id)
    if retry:
        log.info("push.retry", kind=str(kind), attempts=attempts)
        return "retried" if attempts < rules.PUSH_ATTEMPTS else "dropped"
    return "sent" if any(o == "sent" for _, o in outcomes) else "gone"


def _named(kind: Kind, payload: dict[str, Any]) -> UUID | None:
    if "user_id" not in rules.PUSHED_FIELDS[kind]:
        return None
    raw = payload.get("user_id")
    try:
        return UUID(str(raw)) if raw is not None else None
    except ValueError:
        return None


async def _settle(
    sessionmaker: async_sessionmaker[AsyncSession], outbox_id: UUID, outcome: str
) -> str:
    async with sessionmaker() as session, session.begin():
        await repository.finish(session, outbox_id)
    return outcome
