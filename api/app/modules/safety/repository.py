"""SQL for safety records. No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.modules.discovery.repository import main_photo_key
from app.modules.messages.models import Message
from app.modules.profiles.models import Profile
from app.modules.safety.models import Block, FraudEvent, Report
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.verification.repository import badge_of


def add_fraud_event(session: AsyncSession, event: FraudEvent) -> None:
    session.add(event)


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
