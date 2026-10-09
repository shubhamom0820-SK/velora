"""SQL for messages (T-7.1, T-7.3, T-7.5). No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Row,
    case,
    exists,
    func,
    insert,
    literal,
    or_,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.core.enums import Gender, LedgerReason, MessageKind, UserStatus
from app.modules.discovery.repository import blocked_either_way
from app.modules.messages.models import Message, MessageUnlock
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from app.modules.wallet.rules import RefType


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


def _normalised(text: ColumnElement[str]) -> ColumnElement[str]:
    """Case and spacing ignored: "Hi  there" is "hi there"."""
    return func.lower(func.regexp_replace(func.btrim(text), r"\s+", " ", "g"))


async def same_first_messages(
    session: AsyncSession, sender_id: UUID, text: str, since: datetime
) -> int:
    """In how many Threads `sender_id`'s first message since `since` was
    `text`, case and spacing ignored (T-9.2): a Thread's first message, by
    anyone, that was theirs. Compared as written, before any masking."""
    earlier = aliased(Message)
    found = await session.scalar(
        select(func.count(Message.thread_id.distinct())).where(
            Message.sender_id == sender_id,
            Message.kind == MessageKind.TEXT,
            Message.created_at >= since,
            _normalised(func.coalesce(Message.body_raw, Message.body))
            == _normalised(literal(text)),
            ~exists().where(
                earlier.thread_id == Message.thread_id,
                earlier.created_at < Message.created_at,
            ),
        )
    )
    return int(found or 0)


async def add_voice(
    session: AsyncSession,
    *,
    message_id: UUID,
    thread_id: UUID,
    sender_id: UUID,
    media_key: str,
    duration_s: int,
    client_msg_id: UUID,
) -> Message:
    """A voice note, written now, under the id its upload URL gave (T-7.9)."""
    row: Message | None = await session.scalar(
        insert(Message)
        .values(
            id=message_id,
            thread_id=thread_id,
            sender_id=sender_id,
            kind=MessageKind.VOICE,
            media_key=media_key,
            duration_s=duration_s,
            client_msg_id=client_msg_id,
        )
        .returning(Message)
    )
    assert row is not None
    return row


async def message_exists(session: AsyncSession, message_id: UUID) -> bool:
    found = await session.scalar(select(exists().where(Message.id == message_id)))
    return bool(found)


async def voice_of(
    session: AsyncSession, message_id: UUID, viewer_id: UUID
) -> Message | None:
    """The voice note, if it is in a Thread the viewer is one of and no block
    stands between its two."""
    found: Message | None = await session.scalar(
        select(Message)
        .join(Thread, Thread.id == Message.thread_id)
        .where(
            Message.id == message_id,
            Message.kind == MessageKind.VOICE,
            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),
            ~blocked_either_way(viewer_id, _other(viewer_id)),
        )
    )
    return found


async def add_unlock(session: AsyncSession, user_id: UUID, message_id: UUID) -> bool:
    """Record the unlock; False if it was already there. A second at once
    waits on the first's row, then finds it (the primary key)."""
    added = await session.scalar(
        pg_insert(MessageUnlock)
        .values(user_id=user_id, message_id=message_id)
        .on_conflict_do_nothing()
        .returning(MessageUnlock.message_id)
    )
    return added is not None


async def has_unlocked(session: AsyncSession, user_id: UUID, message_id: UUID) -> bool:
    found = await session.scalar(
        select(
            exists().where(
                MessageUnlock.user_id == user_id, MessageUnlock.message_id == message_id
            )
        )
    )
    return bool(found)


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


async def has_paid(
    session: AsyncSession,
    thread_id: UUID,
    user_id: UUID,
    reasons: Collection[LedgerReason],
) -> bool:
    """Whether `user_id` has a ledger entry for one of `reasons` naming this
    Thread."""
    found = await session.scalar(
        select(
            exists().where(
                LedgerEntry.user_id == user_id,
                LedgerEntry.reason.in_(reasons),
                LedgerEntry.ref_type == RefType.THREAD.value,
                LedgerEntry.ref_id == thread_id,
            )
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


async def message_in(
    session: AsyncSession, thread_id: UUID, message_id: UUID
) -> Message | None:
    found: Message | None = await session.scalar(
        select(Message).where(Message.id == message_id, Message.thread_id == thread_id)
    )
    return found


async def mark_read(
    session: AsyncSession,
    thread_id: UUID,
    reader_id: UUID,
    *,
    up_to: tuple[datetime, UUID],
    since: datetime | None,
    at: datetime,
) -> list[tuple[datetime, UUID]]:
    """Set `read_at = at` on the other person's messages in the Thread not yet
    read, up to and including `up_to` by `(created_at, id)`, newer than
    `since` (the reader's clearing). Each marked row's `(created_at, id)`, so
    the caller can name the newest."""
    conditions = [
        Message.thread_id == thread_id,
        Message.sender_id != reader_id,
        Message.read_at.is_(None),
        tuple_(Message.created_at, Message.id) <= up_to,
    ]
    if since is not None:
        conditions.append(Message.created_at > since)
    rows = await session.execute(
        update(Message)
        .where(*conditions)
        .values(read_at=at)
        .returning(Message.created_at, Message.id)
    )
    return [(row.created_at, row.id) for row in rows]
