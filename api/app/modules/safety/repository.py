"""SQL for safety records. No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, Uuid, and_, cast, exists, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.core.enums import FraudBand
from app.modules.discovery.repository import blocked_either_way, main_photo_key
from app.modules.messages.models import Message
from app.modules.profiles.models import Profile
from app.modules.safety.models import Block, FraudEvent, FraudScore, Report
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.verification.repository import badge_of


def add_fraud_event(session: AsyncSession, event: FraudEvent) -> None:
    session.add(event)


# --- Fraud scoring (T-9.2) -----------------------------------------------------------


async def has_signal_since(
    session: AsyncSession, user_id: UUID, signal: str, since: datetime
) -> bool:
    found = await session.scalar(
        select(
            exists().where(
                FraudEvent.user_id == user_id,
                FraudEvent.signal == signal,
                FraudEvent.created_at >= since,
            )
        )
    )
    return bool(found)


async def events_since(
    session: AsyncSession, user_id: UUID, since: datetime
) -> Sequence[Row[Any]]:
    """`user_id`'s signals from `since` on: `(signal, weight, created_at,
    reporter_id)`, the last for a report's, read from the report it names."""
    report_id = cast(FraudEvent.meta["report_id"].astext, Uuid)
    rows = await session.execute(
        select(
            FraudEvent.signal,
            FraudEvent.weight,
            FraudEvent.created_at,
            Report.reporter_id,
        )
        .outerjoin(Report, Report.id == report_id)
        .where(FraudEvent.user_id == user_id, FraudEvent.created_at >= since)
    )
    return rows.all()


async def reporting_numbers(
    session: AsyncSession, user_id: UUID, since: datetime
) -> int:
    """How many numbers reported `user_id` from `since` on, counting only
    reporters who share a Thread with them (D-901): by `phone_hash`, so one
    number's accounts are one."""
    reporter = aliased(User)
    shares_a_thread = exists().where(
        or_(
            and_(Thread.user_low == Report.reporter_id, Thread.user_high == user_id),
            and_(Thread.user_low == user_id, Thread.user_high == Report.reporter_id),
        )
    )
    found = await session.scalar(
        select(func.count(reporter.phone_hash.distinct()))
        .select_from(Report)
        .join(reporter, reporter.id == Report.reporter_id)
        .where(
            Report.reported_id == user_id,
            Report.created_at >= since,
            shares_a_thread,
        )
    )
    return int(found or 0)


async def lock_user(
    session: AsyncSession, user_id: UUID, *, skip_locked: bool = False
) -> User | None:
    """The user's row, locked for the transaction: scoring one person is one
    transaction at a time. With `skip_locked`, None if another holds it.
    `FOR NO KEY UPDATE`, as a status change needs: rows that only point at
    them (a report being filed) aren't held up by it."""
    query = select(User).where(User.id == user_id)
    query = query.with_for_update(key_share=True, skip_locked=skip_locked)
    found: User | None = await session.scalar(query)
    return found


async def score_of(session: AsyncSession, user_id: UUID) -> FraudScore | None:
    found: FraudScore | None = await session.get(FraudScore, user_id)
    return found


async def save_score(
    session: AsyncSession,
    user_id: UUID,
    *,
    score: int,
    band: FraudBand,
    signals: dict[str, int],
    counted_from: datetime | None,
) -> None:
    values = {
        "score": score,
        "band": band,
        "signals": signals,
        "counted_from": counted_from,
    }
    await session.execute(
        insert(FraudScore)
        .values(user_id=user_id, **values)
        .on_conflict_do_update(index_elements=[FraudScore.user_id], set_=values)
    )


async def due_for_scoring(
    session: AsyncSession, since: datetime, *, after: UUID | None, limit: int
) -> Sequence[UUID]:
    """Whose score may have moved: anyone with a signal from `since` on, or a
    score above 0 to decay. By id, from just after `after`."""
    signalled = select(FraudEvent.user_id).where(FraudEvent.created_at >= since)
    scored = select(FraudScore.user_id).where(FraudScore.score > 0)
    ids = signalled.union(scored).subquery()
    query = select(ids.c.user_id).order_by(ids.c.user_id).limit(limit)
    if after is not None:
        query = query.where(ids.c.user_id > after)
    return (await session.scalars(query)).all()


async def user_exists(session: AsyncSession, user_id: UUID) -> bool:
    """Whether any account, in any status, has this id."""
    found = await session.scalar(select(User.id).where(User.id == user_id))
    return found is not None


# --- Blocks (T-9.1) ------------------------------------------------------------------


async def add_block(session: AsyncSession, blocker_id: UUID, blocked_id: UUID) -> None:
    """The pair's standing block, made now unless one already stands: two at
    once are one, by `uq_blocks_active`."""
    await session.execute(
        insert(Block)
        .values(blocker_id=blocker_id, blocked_id=blocked_id)
        .on_conflict_do_nothing(
            index_elements=[Block.blocker_id, Block.blocked_id],
            index_where=Block.unblocked_at.is_(None),
        )
    )


async def lift_block(
    session: AsyncSession, blocker_id: UUID, blocked_id: UUID, now: datetime
) -> None:
    """The pair's standing block, if any, lifted now and kept (D-860)."""
    await session.execute(
        update(Block)
        .where(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id,
            Block.unblocked_at.is_(None),
        )
        .values(unblocked_at=now)
    )


def _standing(blocker_id: UUID) -> Select[Any]:
    """`blocker_id`'s standing blocks, each with the blocked person's
    card-lite columns. An erased person has no profile, so it is joined
    outer: their block is still listed, and still theirs to lift."""
    blocked = aliased(User)
    profile = aliased(Profile)
    return (
        select(
            Block,
            blocked.status.label("blocked_status"),
            blocked.last_active_at.label("blocked_last_active_at"),
            profile.first_name.label("blocked_first_name"),
            profile.username.label("blocked_username"),
            main_photo_key(blocked.id).label("blocked_photo_key"),
            badge_of(blocked.id, blocked.is_verified).label("blocked_badge"),
        )
        .join(blocked, blocked.id == Block.blocked_id)
        .outerjoin(profile, profile.user_id == blocked.id)
        .where(Block.blocker_id == blocker_id, Block.unblocked_at.is_(None))
    )


async def standing_block(
    session: AsyncSession, blocker_id: UUID, blocked_id: UUID
) -> Row[Any]:
    """The pair's standing block, which the caller has just made sure of."""
    return (
        await session.execute(
            _standing(blocker_id).where(Block.blocked_id == blocked_id)
        )
    ).one()


async def standing_blocks(
    session: AsyncSession,
    blocker_id: UUID,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Up to `limit` of `blocker_id`'s standing blocks, newest first by
    `(created_at, blocked_id)`, from just after `after`: one standing block per
    pair, so the key is unique."""
    query = (
        _standing(blocker_id)
        .order_by(Block.created_at.desc(), Block.blocked_id.desc())
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(Block.created_at, Block.blocked_id) < after)
    return (await session.execute(query)).all()


# --- Reports (T-9.1) -----------------------------------------------------------------


async def pair_thread_id(session: AsyncSession, a: UUID, b: UUID) -> UUID | None:
    """The one Thread `a` and `b` have, if any, whatever stands between them."""
    low, high = sorted((a, b))
    found: UUID | None = await session.scalar(
        select(Thread.id).where(Thread.user_low == low, Thread.user_high == high)
    )
    return found


async def add_report(session: AsyncSession, report: Report) -> Report:
    session.add(report)
    await session.flush()
    await session.refresh(report, ["created_at"])
    return report


async def filed_reports(
    session: AsyncSession,
    reporter_id: UUID,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Up to `limit` of the reports `reporter_id` filed, newest first by
    `(created_at, id)`, from just after `after`, each with the reported
    person's card-lite columns and whether a block stands between the two,
    either way (T-9.8). Never a report about them, and never what moderation
    did with one. An erased person has no profile, so it is joined outer."""
    reported = aliased(User)
    profile = aliased(Profile)
    query = (
        select(
            Report.id,
            Report.reason,
            Report.created_at,
            reported.id.label("reported_id"),
            reported.status.label("reported_status"),
            reported.last_active_at.label("reported_last_active_at"),
            profile.first_name.label("reported_first_name"),
            profile.username.label("reported_username"),
            main_photo_key(reported.id).label("reported_photo_key"),
            badge_of(reported.id, reported.is_verified).label("reported_badge"),
            blocked_either_way(reporter_id, reported.id).label("blocked"),
        )
        .join(reported, reported.id == Report.reported_id)
        .outerjoin(profile, profile.user_id == reported.id)
        .where(Report.reporter_id == reporter_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(Report.created_at, Report.id) < after)
    return (await session.execute(query)).all()


async def report_thread_id(session: AsyncSession, report_id: UUID) -> UUID | None:
    found: UUID | None = await session.scalar(
        select(Report.thread_id).where(Report.id == report_id)
    )
    return found


async def thread_messages(session: AsyncSession, thread_id: UUID) -> Sequence[Message]:
    """**A report's evidence** (T-9.1, D-006, D-610): every message of the
    Thread, oldest first, read from `messages` by `thread_id` alone. Never
    through anything that applies a `thread_clears.cleared_at`, which is one
    person's view, and never across a block's hiding, which is the reader's:
    moderation reads the whole Thread, `body_raw` included."""
    rows = await session.scalars(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at, Message.id)
    )
    return rows.all()
