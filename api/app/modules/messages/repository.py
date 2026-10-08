"""SQL for messages (T-7.1, T-7.3). No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, case, exists, insert, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, MessageKind, UserStatus
from app.modules.discovery.repository import blocked_either_way
from app.modules.messages.models import Message, MessageUnlock
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User


async def add_text(
    session: AsyncSession,
    *,
    thread_id: UUID,
    sender_id: UUID,
    body: str,
    body_raw: str | None,
    masked: bool,
    client_msg_id: UUID,
) -> Message:
    """A text message, written now; its row as stored, `created_at` included."""
    row: Message | None = await session.scalar(
        insert(Message)
        .values(
            thread_id=thread_id,
            sender_id=sender_id,
            kind=MessageKind.TEXT,
            body=body,
            body_raw=body_raw,
            masked=masked,
            client_msg_id=client_msg_id,
        )
        .returning(Message)
    )
    assert row is not None
    return row


def _other(viewer_id: UUID) -> Any:
    return case((Thread.user_low == viewer_id, Thread.user_high), else_=Thread.user_low)


async def thread_of(
    session: AsyncSession, thread_id: UUID, viewer_id: UUID, *, lock: bool = False
) -> Thread | None:
    """The Thread, if the viewer is one of its two and no block stands between
    them; with `lock`, held until the transaction ends, so its sends are one
    after the other."""
    query = select(Thread).where(
        Thread.id == thread_id,
        or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),
        ~blocked_either_way(viewer_id, _other(viewer_id)),
    )
    if lock:
        query = query.with_for_update(of=Thread).execution_options(
            populate_existing=True
        )
    found: Thread | None = await session.scalar(query)
    return found


async def by_client_id(
    session: AsyncSession, sender_id: UUID, client_msg_id: UUID
) -> Message | None:
    found: Message | None = await session.scalar(
        select(Message).where(
            Message.sender_id == sender_id, Message.client_msg_id == client_msg_id
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


async def cleared_at(
    session: AsyncSession, thread_id: UUID, viewer_id: UUID
) -> datetime | None:
    found: datetime | None = await session.scalar(
        select(ThreadClear.cleared_at).where(
            ThreadClear.user_id == viewer_id, ThreadClear.thread_id == thread_id
        )
    )
    return found


async def page(
    session: AsyncSession,
    thread_id: UUID,
    viewer_id: UUID,
    *,
    since: datetime | None,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Up to `limit` of the Thread's messages, newest first by
    `(created_at, id)`, from just after `after`, only those newer than `since`
    (the viewer's clearing). Each with whether its sender deleted their
    account, and whether the viewer has unlocked it."""
    sender = select(User.status).where(User.id == Message.sender_id).scalar_subquery()
    unlocked = exists().where(
        MessageUnlock.message_id == Message.id, MessageUnlock.user_id == viewer_id
    )
    query = (
        select(
            Message,
            (sender == UserStatus.DELETED).label("from_deleted_account"),
            unlocked.label("unlocked"),
        )
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    if since is not None:
        query = query.where(Message.created_at > since)
    if after is not None:
        query = query.where(tuple_(Message.created_at, Message.id) < after)
    return (await session.execute(query)).all()


async def gender_of(session: AsyncSession, user_id: UUID) -> Gender | None:
    gender: Gender | None = await session.scalar(
        select(User.gender).where(User.id == user_id)
    )
    return gender
