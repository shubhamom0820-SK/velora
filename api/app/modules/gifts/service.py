"""Gifts (T-8.9): the catalogue, sending one, and what she received.

**Sending** (`POST /gifts/send`): a man sends one of the four gifts to a woman
he could send a private message to (D-550's reach), from her profile. Nothing
about it opens a Thread or unlocks anything (D-016, D-003). In order:

1. Only a man sends (D-016): anyone else is `NOT_ALLOWED`, before anything is
   read. A frozen man never gets here (`ACCOUNT_FROZEN`, `deps.current_user`).
2. One transaction, holding the sender's lock, so two sends at once are one
   after the other:
   - **The same `Idempotency-Key`** returns that send, nothing new; with
     another gift or woman, `ALREADY_EXISTS` (as an order's key, D-481).
   - **Whom:** someone he can't reach as a private message can is `NOT_FOUND`,
     the same answer as an id nobody holds, so a block is never revealed
     (D-493, D-653); someone he can reach who isn't a woman, `NOT_ALLOWED`.
   - **Which:** a gift not on sale (retired, or none) is `NOT_FOUND`.
   - **The cooldown:** the same gift to the same woman inside
     `gift_same_recipient_cooldown_h` is `GIFT_COOLDOWN` (D-016).
   - **The price:** 0 while this week's free sends last (D-231; the week from
     Monday 00:00 IST, D-650), then the gift row's own price, read now. Not
     the price the screen showed: `PRICE_CHANGED`, before anything is written
     (P-56, D-600).
   - The send, then the debit if the price is above 0, in the same
     transaction (rule 5): a refused debit takes the send with it. A free send
     moves no Vela and writes no ledger row (D-231).
   - A live or knotted Thread between them is linked; none is ever opened.
   - She is told: `gift.received` and a `gift` notification. Which setting
     governs its push is T-9.4's (P-550).

`_send_in` is one of the two callers `wallet.service.debit()` answers to
(P-152, D-651), beside `pricing.service.charge`: it prices from `gifts`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.config import Settings
from app.core.enums import Gender, LedgerReason, UserStatus
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.core.storage_keys import public_url
from app.modules.admin import service as admin_service
from app.modules.admin.service import CACHED_FOR
from app.modules.discovery import rules as discovery_rules
from app.modules.discovery import service as discovery_service
from app.modules.gifts import repository, rules, schemas
from app.modules.gifts.models import GiftSend
from app.modules.notifications import repository as notifications_repository
from app.modules.pricing import service as pricing_service
from app.modules.threads import repository as threads_repository
from app.modules.threads import rules as threads_rules
from app.modules.threads.schemas import CardLite
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType

GIFT_RECEIVED = "gift.received"
GIFT_NOTIFICATION = "gift"


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def _not_allowed() -> AppError:
    return AppError("NOT_ALLOWED", "Gifts go from a man to a woman.", status=422)


# --- The catalogue -----------------------------------------------------------------


@dataclass
class GiftCache:
    """The catalogue read in the last `CACHED_FOR` (60 s), one per app
    (`app.state.gift_cache`), as `ConfigCache` is (P-47). Only what is shown:
    a send reads its gift's price fresh, inside its own transaction."""

    gifts: list[schemas.Gift] | None = None
    at: datetime | None = None


async def _gifts(session: AsyncSession, cache: GiftCache) -> list[schemas.Gift]:
    now = clock.now()
    if cache.gifts is not None and cache.at is not None and now - cache.at < CACHED_FOR:
        return cache.gifts
    rows = await repository.active_gifts(session)
    cache.gifts = [
        schemas.Gift(id=row.id, label=row.label, asset=row.asset, credits=row.credits)
        for row in rows
    ]
    cache.at = now
    return cache.gifts


async def catalogue(
    session: AsyncSession,
    user: User,
    cache: GiftCache,
    *,
    config: admin_service.ConfigCache | None = None,
) -> schemas.GiftCatalogue:
    """`GET /gifts` (D-652): the gifts on sale, and for a man the week's free
    sends left, read fresh, with when they come back."""
    async with session.begin():
        gifts = await _gifts(session, cache)
        if user.gender is not Gender.MALE:
            return schemas.GiftCatalogue(
                gifts=gifts, free_sends_left=None, free_sends_reset_at=None
            )
        now = clock.now()
        limit = await admin_service.config_int(
            session, rules.FREE_WEEKLY_KEY, cache=config
        )
        used = await repository.free_used_since(session, user.id, rules.week_start(now))
        return schemas.GiftCatalogue(
            gifts=gifts,
            free_sends_left=rules.free_left(used, limit),
            free_sends_reset_at=rules.next_week_start(now),
        )


# --- Sending -----------------------------------------------------------------------


def view_of(row: GiftSend) -> schemas.GiftSend:
    return schemas.GiftSend(
        id=row.id,
        gift_id=row.gift_id,
        recipient_id=row.recipient_id,
        credits_charged=row.credits_charged,
        thread_id=row.thread_id,
        created_at=row.created_at,
    )


async def send_gift(
    session: AsyncSession,
    user: User,
    request: schemas.SendGiftRequest,
    *,
    key: str,
    config: admin_service.ConfigCache | None = None,
) -> schemas.GiftSend:
    if user.gender is not Gender.MALE:
        raise _not_allowed()
    async with session.begin():
        return await _send_in(session, user, request, key=key, config=config)


async def _send_in(
    session: AsyncSession,
    user: User,
    request: schemas.SendGiftRequest,
    *,
    key: str,
    config: admin_service.ConfigCache | None,
) -> schemas.GiftSend:
    """The send, in the caller's transaction, under the sender's lock."""
    await repository.lock_sender(session, user.id)
    existing = await repository.by_key(session, user.id, key)
    if existing is not None:
        if (existing.recipient_id, existing.gift_id) != (
            request.recipient_id,
            request.gift_id,
        ):
            raise AppError(
                "ALREADY_EXISTS",
                "This request was already used for another gift.",
                status=409,
            )
        return view_of(existing)

    recipient_id = request.recipient_id
    if recipient_id == user.id or not await discovery_service.can_reach(
        session, user, recipient_id, mutual=True
    ):
        raise _not_found()
    if await threads_repository.gender_of(session, recipient_id) is not Gender.FEMALE:
        raise _not_allowed()
    gift = await repository.gift(session, request.gift_id)
    if gift is None or not gift.active:
        raise _not_found()

    now = clock.now()
    hours = await admin_service.config_int(session, rules.COOLDOWN_KEY, cache=config)
    last = await repository.last_sent(session, user.id, recipient_id, gift.id)
    if wait := rules.cooldown_left(last, now, hours):
        raise rules.cooldown(wait)

    limit = await admin_service.config_int(session, rules.FREE_WEEKLY_KEY, cache=config)
    used = await repository.free_used_since(session, user.id, rules.week_start(now))
    price = rules.price_of(gift.credits, free_used=used, free_limit=limit)
    if price != request.shown_price:
        raise pricing_service.price_changed(price)

    row = await repository.add(
        session,
        sender_id=user.id,
        recipient_id=recipient_id,
        gift_id=gift.id,
        credits_charged=price,
        thread_id=await _live_thread(session, user.id, recipient_id, now),
        key=key,
        at=now,
    )
    if price > 0:
        await wallet_service.debit(
            session,
            user.id,
            price,
            LedgerReason.GIFT,
            ref=Ref(RefType.GIFT_SEND, row.id),
        )
    payload = {
        "gift_send_id": str(row.id),
        "gift_id": gift.id,
        "user_id": str(user.id),
    }
    events.queue(session, recipient_id, GIFT_RECEIVED, payload)
    notifications_repository.add(session, recipient_id, GIFT_NOTIFICATION, payload)
    return view_of(row)


async def _live_thread(
    session: AsyncSession, a: UUID, b: UUID, now: datetime
) -> UUID | None:
    """The pair's Thread if it is live or knotted (an expired one is read by
    the clock, D-560); a gift never opens one."""
    thread = await threads_repository.pair_thread(session, a, b)
    if thread is None or threads_rules.has_expired(thread, now):
        return None
    return thread.id


# --- What she received ---------------------------------------------------------------

# `(created_at, id)`, newest first.
RECEIVED_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


async def received(
    session: AsyncSession, user: User, *, params: PageParams, settings: Settings
) -> schemas.ReceivedGiftPage:
    """`GET /me/gifts`: the gifts `user` received, newest first, each with its
    sender's card and never what he paid (D-652); none from across a block."""
    after = None if params.cursor is None else RECEIVED_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.received(
            session, user.id, after=after, limit=params.fetch
        )
    now = clock.now()
    return schemas.ReceivedGiftPage.of(
        _received(rows, now, settings),
        params,
        lambda item: RECEIVED_CURSOR.encode((item.created_at, item.id)),
    )


def _received(
    rows: Sequence[Any], now: datetime, settings: Settings
) -> list[schemas.ReceivedGift]:
    return [
        schemas.ReceivedGift(
            id=row.GiftSend.id,
            gift_id=row.GiftSend.gift_id,
            sender=_sender_card(row, now, settings),
            created_at=row.GiftSend.created_at,
        )
        for row in rows
    ]


def _sender_card(row: Any, now: datetime, settings: Settings) -> CardLite:
    """The sender as a card, as a Thread's row shows the other person: a
    deleted account has no name, username or photo (D-051, D-500)."""
    deleted = row.sender_status is UserStatus.DELETED
    return CardLite(
        id=row.GiftSend.sender_id,
        first_name=None if deleted else row.sender_first_name,
        username=None if deleted else row.sender_username,
        main_photo_url=None
        if deleted or row.sender_photo_key is None
        else public_url(settings, row.sender_photo_key),
        shows_badge=not deleted and bool(row.sender_badge),
        is_online=not deleted
        and row.sender_last_active_at is not None
        and row.sender_last_active_at >= now - discovery_rules.ONLINE_FOR,
        deleted=deleted,
    )


async def counts(
    session: AsyncSession, user: User, user_id: UUID
) -> schemas.GiftCounts:
    """`GET /users/{id}/gifts`: how many of each gift `user_id` received.
    Anyone `user` can't open under D-493 is `NOT_FOUND`; with `show_gifts`
    off, the counts are empty to everyone but herself."""
    async with session.begin():
        if user_id != user.id:
            if not await discovery_service.can_reach(
                session, user, user_id, mutual=False
            ):
                raise _not_found()
            if not await repository.shows_gifts(session, user_id):
                return schemas.GiftCounts(counts=[])
        found = await repository.counts(session, user_id)
    return schemas.GiftCounts(
        counts=[schemas.GiftCount(gift_id=g, count=n) for g, n in found]
    )
