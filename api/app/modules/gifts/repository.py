"""SQL for gifts (T-8.9). No rules here: the service decides."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, func, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.discovery.repository import blocked_either_way, main_photo_key
from app.modules.gifts.models import Gift, GiftSend
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.modules.verification.repository import badge_of

# The advisory lock's first key, meaning "a sender's gifts"; the second is the
# sender's hash. Swipes' pairs lock on 64, Threads' on 71, P-55's slots on 55.
SENDER_LOCK = 89


async def active_gifts(session: AsyncSession) -> list[Gift]:
    """The catalogue as it is sold: active gifts, in `sort` order."""
    rows = await session.scalars(
        select(Gift).where(Gift.active).order_by(Gift.sort, Gift.id)
    )
    return list(rows)


async def gift(session: AsyncSession, gift_id: str) -> Gift | None:
    found: Gift | None = await session.get(Gift, gift_id, populate_existing=True)
    return found


async def lock_sender(session: AsyncSession, sender_id: UUID) -> None:
    """Hold the sender's gifts until this transaction ends: two sends at once
    are one after the other, so the second counts the first's free send, sees
    its cooldown, and finds its key."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock, hashtext(CAST(:s AS text)))"),
        {"lock": SENDER_LOCK, "s": str(sender_id)},
    )


async def by_key(session: AsyncSession, sender_id: UUID, key: str) -> GiftSend | None:
    found: GiftSend | None = await session.scalar(
        select(GiftSend).where(
            GiftSend.sender_id == sender_id, GiftSend.idempotency_key == key
        )
    )
    return found


async def last_sent(
    session: AsyncSession, sender_id: UUID, recipient_id: UUID, gift_id: str
) -> datetime | None:
    """When `sender_id` last sent `gift_id` to `recipient_id`, if ever."""
    found: datetime | None = await session.scalar(
        select(GiftSend.created_at)
        .where(
            GiftSend.sender_id == sender_id,
            GiftSend.recipient_id == recipient_id,
            GiftSend.gift_id == gift_id,
        )
        .order_by(GiftSend.created_at.desc())
        .limit(1)
    )
    return found


async def free_used_since(
    session: AsyncSession, sender_id: UUID, since: datetime
) -> int:
    """The sender's free sends (nothing charged) from `since` on."""
    found = await session.scalar(
        select(func.count())
        .select_from(GiftSend)
        .where(
            GiftSend.sender_id == sender_id,
            GiftSend.credits_charged == 0,
            GiftSend.created_at >= since,
        )
    )
    return int(found or 0)


async def add(
    session: AsyncSession,
    *,
    sender_id: UUID,
    recipient_id: UUID,
    gift_id: str,
    credits_charged: int,
    thread_id: UUID | None,
    key: str,
    at: datetime,
) -> GiftSend:
    """The send, flushed so its id names the debit. `at` is the clock's now:
    the cooldown and the week are read from it, so it is never the
    transaction's `now()`."""
    row = GiftSend(
        sender_id=sender_id,
        recipient_id=recipient_id,
        gift_id=gift_id,
        credits_charged=credits_charged,
        thread_id=thread_id,
        idempotency_key=key,
        created_at=at,
    )
    session.add(row)
    await session.flush()
    return row


async def received(
    session: AsyncSession,
    recipient_id: UUID,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Up to `limit` of the gifts `recipient_id` received, newest first by
    `(created_at, id)`, from just after `after`; never one from someone a block
    stands between. Each row: the send and its sender's card-lite columns."""
    sender = aliased(User)
    profile = aliased(Profile)
    query = (
        select(
            GiftSend,
            sender.status.label("sender_status"),
            sender.last_active_at.label("sender_last_active_at"),
            profile.first_name.label("sender_first_name"),
            profile.username.label("sender_username"),
            main_photo_key(sender.id).label("sender_photo_key"),
            badge_of(sender.id, sender.is_verified).label("sender_badge"),
        )
        .join(sender, sender.id == GiftSend.sender_id)
        .join(profile, profile.user_id == sender.id)
        .where(
            GiftSend.recipient_id == recipient_id,
            ~blocked_either_way(recipient_id, sender.id),
        )
        .order_by(GiftSend.created_at.desc(), GiftSend.id.desc())
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(GiftSend.created_at, GiftSend.id) < after)
    return (await session.execute(query)).all()


async def counts(session: AsyncSession, recipient_id: UUID) -> list[tuple[str, int]]:
    """How many of each gift `recipient_id` received, in the catalogue's
    order: who sent them is never in it."""
    rows = await session.execute(
        select(GiftSend.gift_id, func.count())
        .join(Gift, Gift.id == GiftSend.gift_id)
        .where(GiftSend.recipient_id == recipient_id)
        .group_by(GiftSend.gift_id, Gift.sort)
        .order_by(Gift.sort, GiftSend.gift_id)
    )
    return [(gift_id, int(count)) for gift_id, count in rows]


async def shows_gifts(session: AsyncSession, user_id: UUID) -> bool:
    found = await session.scalar(
        select(Profile.show_gifts).where(Profile.user_id == user_id)
    )
    return bool(found)
