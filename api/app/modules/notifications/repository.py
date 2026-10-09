"""SQL for notifications, push subscriptions and the push outbox. No rules here."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Row,
    Text,
    case,
    cast,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, UserStatus
from app.modules.discovery.repository import blocked_either_way
from app.modules.notifications.models import (
    Notification,
    NotificationPrefs,
    PushOutbox,
    PushSubscription,
)
from app.modules.profiles.models import Profile
from app.modules.threads.models import Thread
from app.modules.users.models import User


def add(
    session: AsyncSession, user_id: UUID, kind: str, payload: dict[str, Any]
) -> None:
    """An in-app notification."""
    session.add(Notification(user_id=user_id, kind=kind, payload=payload))


def add_push(
    session: AsyncSession, user_id: UUID, kind: str, payload: dict[str, Any]
) -> None:
    """A push waiting in the outbox."""
    session.add(PushOutbox(user_id=user_id, kind=kind, payload=payload))


async def recipient(
    session: AsyncSession, user_id: UUID, pref: str
) -> Row[tuple[UserStatus, Gender | None, bool | None, bool]] | None:
    """The user's status and gender, whether `pref` lets their push through,
    and whether they have any push subscription."""
    wanted = getattr(NotificationPrefs, pref)
    subscribed = exists().where(PushSubscription.user_id == User.id)
    query = (
        select(User.status, User.gender, wanted, subscribed)
        .outerjoin(NotificationPrefs, NotificationPrefs.user_id == User.id)
        .where(User.id == user_id)
    )
    return (await session.execute(query)).one_or_none()


# --- The in-app list -------------------------------------------------------------


async def page(
    session: AsyncSession,
    user_id: UUID,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Notification]:
    """Up to `limit` of the user's notifications, newest first by
    `(created_at, id)`, from just after `after`. None about someone either of
    the two has blocked (P-760): the person a row names, by its `user_id`, or
    else the other one in its `thread_id`'s Thread."""
    thread_id = cast(Notification.payload["thread_id"].astext, PG_UUID(as_uuid=True))
    other_in_thread = case(
        (Thread.user_low == Notification.user_id, Thread.user_high),
        else_=Thread.user_low,
    )
    about = func.coalesce(
        cast(Notification.payload["user_id"].astext, PG_UUID(as_uuid=True)),
        other_in_thread,
    )
    query = (
        select(Notification)
        .outerjoin(Thread, Thread.id == thread_id)
        .where(
            Notification.user_id == user_id,
            ~blocked_either_way(Notification.user_id, about),
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(Notification.created_at, Notification.id) < after)
    return (await session.scalars(query)).all()


async def mark_read(session: AsyncSession, user_id: UUID, at: datetime) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=at)
    )


# --- Settings --------------------------------------------------------------------


async def prefs_for_update(
    session: AsyncSession, user_id: UUID
) -> NotificationPrefs | None:
    prefs: NotificationPrefs | None = await session.scalar(
        select(NotificationPrefs)
        .where(NotificationPrefs.user_id == user_id)
        .with_for_update()
    )
    return prefs


async def prefs(session: AsyncSession, user_id: UUID) -> NotificationPrefs | None:
    return await session.get(NotificationPrefs, user_id)


# --- Subscriptions ---------------------------------------------------------------


async def subscribe(
    session: AsyncSession, user_id: UUID, endpoint: str, p256dh: str, auth: str
) -> None:
    """The endpoint, now this user's: a browser signed in to another account
    since moves with its subscription, so one endpoint is never pushed twice."""
    await session.execute(
        insert(PushSubscription)
        .values(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        .on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={
                "user_id": user_id,
                "p256dh": p256dh,
                "auth": auth,
                "created_at": func.now(),
                "last_ok_at": None,
            },
        )
    )


async def keep_newest(session: AsyncSession, user_id: UUID, kept: int) -> None:
    """Delete the user's subscriptions beyond the newest `kept`."""
    newest = (
        select(PushSubscription.id)
        .where(PushSubscription.user_id == user_id)
        .order_by(PushSubscription.created_at.desc(), PushSubscription.id.desc())
        .limit(kept)
    )
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.id.not_in(newest)
        )
    )


async def unsubscribe(session: AsyncSession, user_id: UUID, endpoint: str) -> None:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
    )


async def subscriptions(
    session: AsyncSession, user_id: UUID
) -> Sequence[Row[tuple[str, str, str]]]:
    return (
        await session.execute(
            select(
                PushSubscription.endpoint,
                PushSubscription.p256dh,
                PushSubscription.auth,
            ).where(PushSubscription.user_id == user_id)
        )
    ).all()


async def drop_gone(session: AsyncSession, user_id: UUID, endpoint: str) -> None:
    """A subscription the push service says is gone (404, 410)."""
    await unsubscribe(session, user_id, endpoint)


async def mark_ok(
    session: AsyncSession, user_id: UUID, endpoint: str, at: datetime
) -> None:
    await session.execute(
        update(PushSubscription)
        .where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
        .values(last_ok_at=at)
    )


# --- The outbox --------------------------------------------------------------------


async def claim(
    session: AsyncSession, now: datetime, stale_before: datetime, limit: int
) -> Sequence[PushOutbox]:
    """Up to `limit` waiting pushes, oldest first, claimed for this sender: not
    claimed, or claimed before `stale_before` by a sender that never finished.
    Rows another transaction holds are skipped, so two senders take different
    ones."""
    waiting = (
        select(PushOutbox.id)
        .where(
            or_(
                PushOutbox.claimed_at.is_(None),
                PushOutbox.claimed_at < stale_before,
            )
        )
        .order_by(PushOutbox.created_at, PushOutbox.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    claimed = await session.scalars(
        update(PushOutbox)
        .where(PushOutbox.id.in_(waiting))
        .values(claimed_at=now, attempts=PushOutbox.attempts + 1)
        .returning(PushOutbox)
        .execution_options(populate_existing=True)
    )
    return sorted(claimed.all(), key=lambda row: (row.created_at, row.id))


async def finish(session: AsyncSession, outbox_id: UUID) -> None:
    await session.execute(delete(PushOutbox).where(PushOutbox.id == outbox_id))


async def release(session: AsyncSession, outbox_id: UUID) -> None:
    """Back to waiting, for another try."""
    await session.execute(
        update(PushOutbox).where(PushOutbox.id == outbox_id).values(claimed_at=None)
    )


async def push_context(
    session: AsyncSession, user_id: UUID, pref: str, named_id: UUID | None
) -> Row[tuple[UserStatus, bool | None, bool | None, str | None, bool]] | None:
    """For a push about to go: the recipient's status, whether `pref` still
    lets it through, `generic_text`, the first name of `named_id`, and whether
    either has blocked the other since it was written (P-760)."""
    name = (
        select(Profile.first_name).where(Profile.user_id == named_id).scalar_subquery()
        if named_id is not None
        else literal(None, Text)
    )
    query = (
        select(
            User.status,
            getattr(NotificationPrefs, pref),
            NotificationPrefs.generic_text,
            name,
            blocked_either_way(User.id, named_id)
            if named_id is not None
            else literal(False),
        )
        .outerjoin(NotificationPrefs, NotificationPrefs.user_id == User.id)
        .where(User.id == user_id)
    )
    return (await session.execute(query)).one_or_none()
