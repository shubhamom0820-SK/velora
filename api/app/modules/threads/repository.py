"""SQL for threads (T-7.1). No rules here: the service decides."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Uuid, func, insert, literal, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, ThreadOrigin
from app.modules.matches.models import Match
from app.modules.threads.models import Thread
from app.modules.users.models import User

# The advisory lock's first key, meaning "a Thread's pair"; the second is the
# ordered pair's hash. Swipes' pairs lock on 64, P-55's slots on 55.
PAIR_LOCK = 71


async def lock_pair(session: AsyncSession, a: UUID, b: UUID) -> None:
    """Hold the pair until this transaction ends, whoever opens: two taps at
    once are one after the other, and the second finds the first's Thread."""
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock(:lock, hashtext("
            "least(CAST(:a AS uuid), CAST(:b AS uuid))::text"
            " || greatest(CAST(:a AS uuid), CAST(:b AS uuid))::text))"
        ),
        {"lock": PAIR_LOCK, "a": a, "b": b},
    )


def _ordered(a: UUID, b: UUID) -> tuple[object, object]:
    """The pair as the database orders it (`pair_ordered`), never Python."""
    one, two = literal(a, Uuid), literal(b, Uuid)
    return func.least(one, two), func.greatest(one, two)


async def pair_thread(session: AsyncSession, a: UUID, b: UUID) -> Thread | None:
    low, high = _ordered(a, b)
    found: Thread | None = await session.scalar(
        select(Thread).where(Thread.user_low == low, Thread.user_high == high)
    )
    return found


async def my_match(
    session: AsyncSession, match_id: UUID, user_id: UUID
) -> Match | None:
    """The match, if `user_id` is one of its two."""
    found: Match | None = await session.scalar(
        select(Match).where(
            Match.id == match_id,
            or_(Match.user_low == user_id, Match.user_high == user_id),
        )
    )
    return found


async def pair_match(session: AsyncSession, a: UUID, b: UUID) -> Match | None:
    low, high = _ordered(a, b)
    found: Match | None = await session.scalar(
        select(Match).where(Match.user_low == low, Match.user_high == high)
    )
    return found


async def add(
    session: AsyncSession,
    *,
    opened_by: UUID,
    other_id: UUID,
    origin: ThreadOrigin,
    expires_at: datetime | None,
) -> Thread:
    low, high = _ordered(opened_by, other_id)
    row: Thread | None = await session.scalar(
        insert(Thread)
        .values(
            user_low=low,
            user_high=high,
            origin=origin,
            opened_by=opened_by,
            expires_at=expires_at,
        )
        .returning(Thread)
    )
    assert row is not None
    return row


async def link_match(session: AsyncSession, match_id: UUID, thread_id: UUID) -> None:
    """Point the match at its Thread, unless it already points at one."""
    await session.execute(
        update(Match)
        .where(Match.id == match_id, Match.thread_id.is_(None))
        .values(thread_id=thread_id)
    )


async def gender_of(session: AsyncSession, user_id: UUID) -> Gender | None:
    gender: Gender | None = await session.scalar(
        select(User.gender).where(User.id == user_id)
    )
    return gender
