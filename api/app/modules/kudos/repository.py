"""SQL for kudos (T-8.5). No rules here: the service decides."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Kudos as KudosKind
from app.core.enums import UserStatus
from app.modules.discovery.repository import blocked_either_way
from app.modules.kudos.models import Kudos
from app.modules.messages.models import Message
from app.modules.threads.models import Thread
from app.modules.users.models import User


async def thread_between(session: AsyncSession, a: UUID, b: UUID) -> Thread | None:
    """The pair's one Thread, if no block stands between them."""
    low, high = sorted((a, b))
    found: Thread | None = await session.scalar(
        select(Thread).where(
            Thread.user_low == low,
            Thread.user_high == high,
            ~blocked_either_way(a, b),
        )
    )
    return found


async def has_written(session: AsyncSession, thread_id: UUID, user_id: UUID) -> bool:
    found = await session.scalar(
        select(
            exists().where(Message.thread_id == thread_id, Message.sender_id == user_id)
        )
    )
    return bool(found)


async def status_of(session: AsyncSession, user_id: UUID) -> UserStatus | None:
    status: UserStatus | None = await session.scalar(
        select(User.status).where(User.id == user_id)
    )
    return status


async def add(
    session: AsyncSession,
    *,
    from_id: UUID,
    to_id: UUID,
    kind: KudosKind,
    thread_id: UUID,
) -> datetime | None:
    """The kudos, written now, and when; None if this pair already has one
    (`uq_kudos_from_id_to_id`), however close together the two arrived."""
    created_at: datetime | None = await session.scalar(
        insert(Kudos)
        .values(from_id=from_id, to_id=to_id, kind=kind, thread_id=thread_id)
        .on_conflict_do_nothing(index_elements=[Kudos.from_id, Kudos.to_id])
        .returning(Kudos.created_at)
    )
    return created_at


async def given(session: AsyncSession, from_id: UUID, to_id: UUID) -> bool:
    """Whether `from_id` has given `to_id` kudos, of any kind."""
    found = await session.scalar(
        select(exists().where(Kudos.from_id == from_id, Kudos.to_id == to_id))
    )
    return bool(found)


async def received(session: AsyncSession, user_id: UUID) -> dict[KudosKind, int]:
    """How many of each kind `user_id` was given. Never by whom."""
    rows = await session.execute(
        select(Kudos.kind, func.count())
        .where(Kudos.to_id == user_id)
        .group_by(Kudos.kind)
    )
    return {kind: count for kind, count in rows.tuples()}
