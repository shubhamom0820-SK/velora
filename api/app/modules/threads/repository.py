"""SQL for threads (T-7.1, T-7.2, T-7.8). No rules here: the service decides."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Row,
    Text,
    Uuid,
    and_,
    case,
    cast,
    delete,
    func,
    insert,
    literal,
    or_,
    select,
    text,
    true,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import Gender, ThreadOrigin, ThreadStatus, UserStatus
from app.modules.discovery.repository import blocked_either_way, main_photo_key
from app.modules.matches.models import Match
from app.modules.messages.models import Message
from app.modules.profiles.models import Profile
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from app.modules.verification.repository import badge_of

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


# --- The list (T-7.2) ---------------------------------------------------------------


def _other(viewer_id: UUID) -> Any:
    """The other person of each Thread row, as the viewer is one of its two."""
    return case((Thread.user_low == viewer_id, Thread.user_high), else_=Thread.user_low)


def sort_key() -> Any:
    """A Thread's place in the list: its last message, or when it opened."""
    return func.coalesce(Thread.last_message_at, Thread.created_at)


def _cleared_at(viewer_id: UUID) -> Any:
    return (
        select(ThreadClear.cleared_at)
        .where(ThreadClear.user_id == viewer_id, ThreadClear.thread_id == Thread.id)
        .scalar_subquery()
    )


def _unread(viewer_id: UUID) -> Any:
    """The other person's messages I haven't read, newer than my clearing."""
    cleared = _cleared_at(viewer_id)
    return (
        select(func.count())
        .select_from(Message)
        .where(
            Message.thread_id == Thread.id,
            Message.sender_id != viewer_id,
            Message.read_at.is_(None),
            or_(cleared.is_(None), Message.created_at > cleared),
        )
        .scalar_subquery()
    )


def _like(text_: str) -> str:
    """`text_` as an ILIKE pattern that matches it anywhere, literally."""
    escaped = text_.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@dataclass(frozen=True)
class ListFilter:
    knots: bool
    unread_only: bool = False
    # Only Threads with a message at or after this instant.
    since: datetime | None = None
    q: str | None = None


async def rows_for(
    session: AsyncSession,
    viewer_id: UUID,
    which: ListFilter,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Up to `limit` of the viewer's Threads, newest first by `(sort_key, id)`,
    from just after `after`: never one they cleared with nothing newer, never
    one with a block either way. Each row: the Thread, the other person's
    card-lite columns, the unread count and the last message."""
    other_id = _other(viewer_id)
    other = aliased(User)
    profile = aliased(Profile)
    last = (
        select(
            Message.kind.label("last_kind"),
            Message.body.label("last_body"),
            Message.sender_id.label("last_sender_id"),
            Message.created_at.label("last_at"),
        )
        .where(Message.thread_id == Thread.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .lateral()
    )
    cleared = _cleared_at(viewer_id)
    unread = _unread(viewer_id)
    statuses = (
        [ThreadStatus.KNOTTED]
        if which.knots
        else [ThreadStatus.ACTIVE, ThreadStatus.EXPIRED]
    )
    key = sort_key()
    query = (
        select(
            Thread,
            other.id.label("other_id"),
            other.status.label("other_status"),
            other.last_active_at.label("other_last_active_at"),
            profile.first_name.label("other_first_name"),
            profile.username.label("other_username"),
            main_photo_key(other.id).label("other_photo_key"),
            badge_of(other.id, other.is_verified).label("other_badge"),
            unread.label("unread"),
            last.c.last_kind,
            last.c.last_body,
            last.c.last_sender_id,
            last.c.last_at,
            key.label("sort_key"),
        )
        .select_from(Thread)
        .join(other, other.id == other_id)
        .join(profile, profile.user_id == other.id)
        .outerjoin(last, true())
        .where(
            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),
            Thread.status.in_(statuses),
            or_(cleared.is_(None), Thread.last_message_at > cleared),
            ~blocked_either_way(viewer_id, other.id),
        )
        .order_by(key.desc(), Thread.id.desc())
        .limit(limit)
    )
    if which.unread_only:
        query = query.where(unread > 0)
    if which.since is not None:
        query = query.where(Thread.last_message_at >= which.since)
    if which.q:
        pattern = _like(which.q)
        query = query.where(
            other.status != UserStatus.DELETED,
            or_(
                profile.first_name.ilike(pattern, escape="\\"),
                cast(profile.username, Text).ilike(pattern, escape="\\"),
            ),
        )
    if after is not None:
        query = query.where(tuple_(key, Thread.id) < after)
    return (await session.execute(query)).all()


async def my_thread(
    session: AsyncSession, thread_id: UUID, viewer_id: UUID
) -> Thread | None:
    """The Thread, if the viewer is one of its two and no block stands between
    them."""
    found: Thread | None = await session.scalar(
        select(Thread).where(
            Thread.id == thread_id,
            or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),
            ~blocked_either_way(viewer_id, _other(viewer_id)),
        )
    )
    return found


# --- Clearing (T-7.8) ---------------------------------------------------------------


def _mine(viewer_id: UUID) -> Any:
    """The viewer's Threads that no block stands across."""
    return and_(
        or_(Thread.user_low == viewer_id, Thread.user_high == viewer_id),
        ~blocked_either_way(viewer_id, _other(viewer_id)),
    )


async def lock_mine(
    session: AsyncSession, viewer_id: UUID, thread_ids: Sequence[UUID]
) -> list[UUID]:
    """Those of `thread_ids` that are the viewer's, held until the transaction
    ends, as a send holds one: a clear waits for a send under way, and a send
    for the clear. In id order, so two clears never wait on each other."""
    found = await session.scalars(
        select(Thread.id)
        .where(Thread.id.in_(thread_ids), _mine(viewer_id))
        .order_by(Thread.id)
        .with_for_update(of=Thread)
    )
    return list(found)


async def lock_expired(
    session: AsyncSession, viewer_id: UUID, now: datetime
) -> list[UUID]:
    """The viewer's expired Threads in their list, held as `lock_mine` holds
    them. Expired by the clock (D-560): an active Thread whose `expires_at`
    has passed is one, though the cron hasn't caught its status up. One
    already cleared with nothing newer isn't in the list, so isn't here."""
    cleared = _cleared_at(viewer_id)
    found = await session.scalars(
        select(Thread.id)
        .where(
            _mine(viewer_id),
            or_(
                Thread.status == ThreadStatus.EXPIRED,
                and_(Thread.status == ThreadStatus.ACTIVE, Thread.expires_at <= now),
            ),
            # In my list: T-7.2's rule, nothing newer than my clearing hidden.
            or_(Thread.last_message_at > cleared, cleared.is_(None)),
        )
        .order_by(Thread.id)
        .with_for_update(of=Thread)
    )
    return list(found)


async def clear(
    session: AsyncSession, viewer_id: UUID, thread_ids: Sequence[UUID]
) -> None:
    """Clear `thread_ids` for the viewer alone (D-006), each through its newest
    message, or its opening before any (D-610): a message written later, by
    the database's clock as messages are, shows. Call it once the Threads are
    held, in a statement of its own, so it sees what a send it waited for
    wrote. Writes `thread_clears` and nothing else."""
    newest = (
        select(func.max(Message.created_at))
        .where(Message.thread_id == Thread.id)
        .scalar_subquery()
    )
    through = select(
        literal(viewer_id, Uuid), Thread.id, func.coalesce(newest, Thread.created_at)
    ).where(Thread.id.in_(thread_ids))
    upsert = pg_insert(ThreadClear).from_select(
        [ThreadClear.user_id, ThreadClear.thread_id, ThreadClear.cleared_at], through
    )
    await session.execute(
        upsert.on_conflict_do_update(
            index_elements=[ThreadClear.user_id, ThreadClear.thread_id],
            set_={ThreadClear.cleared_at: upsert.excluded.cleared_at},
        )
    )


async def restore(session: AsyncSession, viewer_id: UUID, thread_id: UUID) -> None:
    """The viewer's clearing of the Thread, gone: the whole history shows again
    (D-611). A clearing is a view, never a moderation record (D-503 erases
    them)."""
    await session.execute(
        delete(ThreadClear).where(
            ThreadClear.user_id == viewer_id, ThreadClear.thread_id == thread_id
        )
    )
