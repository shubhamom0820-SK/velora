"""Opening a Thread (T-7.1); listing them (T-7.2); clearing one from your own
chats (T-7.8); its hour bought and run out (T-7.6, at the end).

`POST /v1/threads`, from a match (`thread_open`) or as a private message
(`dm_open`, with its first message; D-231). One Thread per pair, forever: if
there is one, it is returned and nothing is charged, which is also what a
second tap gets. An expired one refuses him (`THREAD_EXPIRED`) and is returned
to her (D-097). Otherwise, in one transaction: the Thread, the charge (a man
pays the price, a woman nothing; D-098), the match pointed at it, the first
message if private, and the other person told (`thread.opened` and a
notification; `message.new` for the message).

Whom: a match's other person, while the public profile's rule still lets you
reach them (D-493); for a private message, someone that rule allows who also
wants your gender, as swipes ask (D-550). Every refusal is `NOT_FOUND`, the
same answer as an id nobody holds: a block is never revealed.

The pair is locked for the transaction, so two taps at once are one after the
other. A woman's daily places (D-098: new men, private messages) are taken
before it and given back if nothing is written.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.config import Settings
from app.core.enums import (
    LedgerReason,
    MessageKind,
    ThreadOrigin,
    ThreadStatus,
    UserStatus,
)
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.core.storage_keys import public_url
from app.modules.admin import service as admin_service
from app.modules.discovery import rules as discovery_rules
from app.modules.discovery import service as discovery_service
from app.modules.messages import limits
from app.modules.messages import service as messages_service
from app.modules.notifications import repository as notifications_repository
from app.modules.pricing import service as pricing_service
from app.modules.threads import repository, rules, schemas
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType

THREAD_OPENED = "thread.opened"
THREAD_NOTIFICATION = "thread"
# T-7.6: to whoever sees the expiry, a man, never her (D-097, D-554).
THREAD_EXPIRING = "thread.expiring"
THREAD_EXPIRED = "thread.expired"
EXPIRING_NOTIFICATION = "thread_expiring"


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def view_of(thread: Thread, viewer: User) -> schemas.Thread:
    """`thread` as `viewer`, one of its two, sees it."""
    low = viewer.id == thread.user_low
    tied = thread.low_knot_at if low else thread.high_knot_at
    return schemas.Thread(
        id=thread.id,
        origin=thread.origin,
        status=thread.status,
        other_user_id=thread.user_high if low else thread.user_low,
        expires_at=thread.expires_at if rules.sees_the_expiry(viewer.gender) else None,
        knotted_at=thread.knotted_at,
        i_tied=tied is not None,
        last_message_at=thread.last_message_at,
        created_at=thread.created_at,
    )


@dataclass(frozen=True)
class _Opened:
    thread: schemas.Thread
    created: bool


async def open_thread(
    session: AsyncSession,
    redis: Redis,
    user: User,
    request: schemas.OpenThreadRequest,
    *,
    config: admin_service.ConfigCache | None = None,
) -> schemas.Thread:
    # Read now: a refusal rolls the session back, which expires `user`.
    user_id, gender = user.id, user.gender
    day = clock.today_ist()
    origin = ThreadOrigin.MATCH if request.match_id is not None else ThreadOrigin.DM
    if request.first_message is not None:
        await messages_service.refuse_if_rejected(
            session, user_id, request.first_message
        )
    new_men = private = None
    async with session.begin():
        other_id = await _other_of(session, user, request)
        if limits.limited(gender) and not await repository.pair_thread(
            session, user_id, other_id
        ):
            if limits.counts_as_a_man(await repository.gender_of(session, other_id)):
                new_men = await admin_service.config_int(
                    session, limits.NEW_MEN_KEY, cache=config
                )
            if origin is ThreadOrigin.DM:
                private = await admin_service.config_int(
                    session, limits.PRIVATE_MESSAGES_KEY, cache=config
                )
    taken = limits.Taken(redis, user_id, day)
    try:
        if new_men is not None:
            await taken.new_man(other_id, new_men)
        if private is not None:
            await taken.private_message(private)
        async with session.begin():
            opened = await _open_in(
                session, user, other_id, origin, request, config=config
            )
    except BaseException:
        await taken.give_back()
        raise
    if not opened.created:
        await taken.give_back()
    return opened.thread


async def _other_of(
    session: AsyncSession, user: User, request: schemas.OpenThreadRequest
) -> UUID:
    """Whom `request` opens a Thread with, if `user` may reach them."""
    if request.match_id is not None:
        match = await repository.my_match(session, request.match_id, user.id)
        if match is None:
            raise _not_found()
        other_id = match.user_high if match.user_low == user.id else match.user_low
        mutual = False
    else:
        assert request.user_id is not None
        other_id, mutual = request.user_id, True
    if other_id == user.id or not await discovery_service.can_reach(
        session, user, other_id, mutual=mutual
    ):
        raise _not_found()
    return other_id


async def _open_in(
    session: AsyncSession,
    user: User,
    other_id: UUID,
    origin: ThreadOrigin,
    request: schemas.OpenThreadRequest,
    *,
    config: admin_service.ConfigCache | None,
) -> _Opened:
    """The Thread, found or opened, in the caller's transaction."""
    await repository.lock_pair(session, user.id, other_id)
    # Again, under the lock: a block or a freeze may have landed since.
    if not await discovery_service.can_reach(
        session, user, other_id, mutual=origin is ThreadOrigin.DM
    ):
        raise _not_found()
    match = await repository.pair_match(session, user.id, other_id)
    existing = await repository.pair_thread(session, user.id, other_id)
    if existing is not None:
        if rules.has_expired(existing, clock.now()) and not (
            rules.passes_an_expired_thread(user.gender)
        ):
            raise rules.thread_expired()
        if match is not None:
            await repository.link_match(session, match.id, existing.id)
        return _Opened(view_of(existing, user), created=False)

    hours = await admin_service.config_int(
        session, rules.THREAD_HOURS_KEY, cache=config
    )
    thread = await repository.add(
        session,
        opened_by=user.id,
        other_id=other_id,
        origin=origin,
        expires_at=rules.expires_at(origin, clock.now(), hours),
    )
    await pricing_service.charge(
        session,
        user,
        rules.OPEN_PRICE[origin],
        shown=request.shown_price,
        ref=Ref(RefType.THREAD, thread.id),
    )
    if match is not None:
        await repository.link_match(session, match.id, thread.id)
    payload = {"thread_id": str(thread.id), "user_id": str(user.id)}
    events.queue(session, other_id, THREAD_OPENED, payload)
    notifications_repository.add(session, other_id, THREAD_NOTIFICATION, payload)
    if request.first_message is not None:
        mask_first_n = await admin_service.config_int(
            session, messages_service.MASK_KEY, cache=config
        )
        row = await messages_service.write_text(
            session,
            thread,
            user.id,
            request.first_message,
            uuid.uuid4(),
            mask_first_n=mask_first_n,
        )
        messages_service.announce(session, row, other_id)
    return _Opened(view_of(thread, user), created=True)


# --- The list (T-7.2) ---------------------------------------------------------------

# `(sort_key, id)`: the last message's time, or the opening's before any.
LIST_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])

Tier = Literal["threads", "knots"]
Filter = Literal["all", "unread", "recent"]


async def list_threads(
    session: AsyncSession,
    user: User,
    *,
    tier: Tier,
    filter_: Filter,
    q: str | None,
    params: PageParams,
    settings: Settings,
) -> schemas.ThreadRowPage:
    """`user`'s Threads (`threads`: active and expired) or Knots, newest first:
    never one they cleared with nothing newer, never one with a block either
    way (T-7.2). `unread` keeps those with a message they haven't read;
    `recent`, those with one in the last three days; `q`, the other person's
    first name or username, anywhere in it."""
    after = None if params.cursor is None else LIST_CURSOR.decode(params.cursor)
    now = clock.now()
    which = repository.ListFilter(
        knots=tier == "knots",
        unread_only=filter_ == "unread",
        since=now - rules.RECENT_FOR if filter_ == "recent" else None,
        q=q,
    )
    async with session.begin():
        rows = await repository.rows_for(
            session, user.id, which, after=after, limit=params.fetch
        )
    keys = {row.Thread.id: row.sort_key for row in rows}
    return schemas.ThreadRowPage.of(
        _rows(rows, user, now, settings),
        params,
        lambda item: LIST_CURSOR.encode((keys[item.id], item.id)),
    )


def _rows(
    rows: Sequence[Any], user: User, now: datetime, settings: Settings
) -> list[schemas.ThreadRow]:
    return [_row_of(row, user, now, settings) for row in rows]


def _row_of(
    row: Any, user: User, now: datetime, settings: Settings
) -> schemas.ThreadRow:
    thread = view_of(row.Thread, user)
    deleted = row.other_status is UserStatus.DELETED
    other = schemas.CardLite(
        id=row.other_id,
        first_name=None if deleted else row.other_first_name,
        username=None if deleted else row.other_username,
        main_photo_url=None
        if deleted or row.other_photo_key is None
        else public_url(settings, row.other_photo_key),
        shows_badge=not deleted and bool(row.other_badge),
        is_online=not deleted
        and row.other_last_active_at is not None
        and row.other_last_active_at >= now - discovery_rules.ONLINE_FOR,
        deleted=deleted,
    )
    last = (
        None
        if row.last_kind is None
        else schemas.LastMessage(
            kind=row.last_kind,
            text=row.last_body[: rules.PREVIEW_CHARS]
            if row.last_kind is MessageKind.TEXT and row.last_body is not None
            else None,
            mine=row.last_sender_id == user.id,
            at=row.last_at,
        )
    )
    return schemas.ThreadRow(
        id=thread.id,
        origin=thread.origin,
        status=thread.status,
        expires_at=thread.expires_at,
        knotted_at=thread.knotted_at,
        i_tied=thread.i_tied,
        unread=row.unread,
        last_message=last,
        last_message_at=thread.last_message_at,
        other=other,
    )


async def get_thread(
    session: AsyncSession, user: User, thread_id: UUID
) -> schemas.Thread:
    """One of `user`'s Threads; anyone else's, or one a block stands across,
    is `NOT_FOUND`."""
    async with session.begin():
        thread = await repository.my_thread(session, thread_id, user.id)
        if thread is None:
            raise _not_found()
        return view_of(thread, user)


# --- Clearing (T-7.8) ---------------------------------------------------------------


async def clear(session: AsyncSession, user: User, thread_id: UUID) -> None:
    """Clear one of `user`'s Threads from their chats, theirs alone (D-006):
    the other person, the messages and the Thread itself are as they were.
    Again changes nothing. Anyone else's, or one across a block, is
    `NOT_FOUND`."""
    async with session.begin():
        if not await repository.lock_mine(session, user.id, [thread_id]):
            raise _not_found()
        await repository.clear(session, user.id, [thread_id])


async def clear_many(
    session: AsyncSession, user: User, request: schemas.ClearThreadsRequest
) -> schemas.Cleared:
    """Clear the chosen Threads, or every expired one in `user`'s list, at
    once. An id that isn't theirs, or is across a block, is skipped and not
    counted: one block landing in select mode never refuses the rest."""
    async with session.begin():
        if request.expired:
            ids = await repository.lock_expired(session, user.id, clock.now())
        else:
            assert request.thread_ids is not None
            ids = await repository.lock_mine(
                session, user.id, sorted(set(request.thread_ids))
            )
        if ids:
            await repository.clear(session, user.id, ids)
    return schemas.Cleared(cleared=len(ids))


async def restore(session: AsyncSession, user: User, thread_id: UUID) -> None:
    """Undo `user`'s clearing of a Thread: its whole history shows again
    (D-611). One never cleared changes nothing. Anyone else's, or one across a
    block, is `NOT_FOUND`."""
    async with session.begin():
        if await repository.my_thread(session, thread_id, user.id) is None:
            raise _not_found()
        await repository.restore(session, user.id, thread_id)


# --- The hour, bought and run out (T-7.6) -------------------------------------------

# Threads a sweep takes in one transaction; it goes on until a batch comes back
# short.
SWEEP_BATCH = 500


async def reopen(
    session: AsyncSession,
    user: User,
    thread_id: UUID,
    *,
    key: str,
    shown_price: int,
    config: admin_service.ConfigCache | None = None,
) -> schemas.Thread:
    """`POST /threads/{id}/reopen`: an expired Thread, his again for an hour
    from now, for `thread_reopen` (D-097 step 4, D-098; T-7.6's answer 1). A
    live one is returned as it is, nothing charged (D-642)."""
    return await _buy_time(
        session,
        user,
        thread_id,
        LedgerReason.THREAD_REOPEN,
        key=key,
        shown_price=shown_price,
        config=config,
    )


async def extend(
    session: AsyncSession,
    user: User,
    thread_id: UUID,
    *,
    key: str,
    shown_price: int,
    config: admin_service.ConfigCache | None = None,
) -> schemas.Thread:
    """`POST /threads/{id}/extend`: `thread_extend_hours` more, on top of what
    is left, for `thread_extend`, as often as he likes (D-250); from expired the
    same price re-opens it too, one debit, never a re-open beside it (D-253)."""
    return await _buy_time(
        session,
        user,
        thread_id,
        LedgerReason.THREAD_EXTEND,
        key=key,
        shown_price=shown_price,
        config=config,
    )


async def _buy_time(
    session: AsyncSession,
    user: User,
    thread_id: UUID,
    reason: LedgerReason,
    *,
    key: str,
    shown_price: int,
    config: admin_service.ConfigCache | None,
) -> schemas.Thread:
    """In one transaction, holding the Thread: the same `Idempotency-Key` again
    returns the Thread, nothing charged and the hour not moved; then who may
    buy, what the Thread allows, the charge at the price he was shown (P-56,
    D-600), and the hour moved, the Thread `active` and its warning cleared
    (D-560)."""
    user_id, gender = user.id, user.gender
    async with session.begin():
        thread = await repository.my_thread(session, thread_id, user_id, lock=True)
        if thread is None:
            raise _not_found()
        event = rules.time_event(reason, thread.id, key)
        if await wallet_service.entry_for(session, user_id, reason, event) is not None:
            return view_of(thread, user)
        if not rules.buys_time(gender) or not rules.has_an_hour(thread):
            raise rules.not_allowed()
        now = clock.now()
        if reason is LedgerReason.THREAD_REOPEN:
            if not rules.has_expired(thread, now):
                return view_of(thread, user)
            hours = await admin_service.config_int(
                session, rules.THREAD_HOURS_KEY, cache=config
            )
            until = rules.reopened_until(now, hours)
        else:
            hours = await admin_service.config_int(
                session, rules.THREAD_EXTEND_HOURS_KEY, cache=config
            )
            until = rules.extended_until(thread, now, hours)
        await pricing_service.charge(
            session,
            user,
            reason,
            shown=shown_price,
            ref=Ref(RefType.THREAD, thread.id),
            event=event,
        )
        thread.status = ThreadStatus.ACTIVE
        thread.expires_at = until
        thread.expiry_warned_at = None
        return view_of(thread, user)


async def expire_batch(session: AsyncSession, *, limit: int = SWEEP_BATCH) -> int:
    """One transaction of the expiry sweep: active Threads past `expires_at`
    marked `expired`, and `thread.expired` to whoever of the two sees the
    expiry, never her (D-097). How many it took."""
    async with session.begin():
        rows = await repository.expire_due(session, clock.now(), limit=limit)
        await _tell(session, rows, THREAD_EXPIRED, lambda row: {})
    return len(rows)


async def warn_batch(
    session: AsyncSession,
    *,
    limit: int = SWEEP_BATCH,
    config: admin_service.ConfigCache | None = None,
) -> int:
    """One transaction of the warning sweep: active Threads with
    `thread_warn_minutes` or less left and not yet warned for this expiry,
    marked warned, and `thread.expiring` and a notification to whoever of the
    two sees the expiry, never her (T-7.6's answer 2). Every move of the hour
    clears the mark, so each expiry gets its one warning. How many it took."""
    async with session.begin():
        minutes = await admin_service.config_int(
            session, rules.THREAD_WARN_MINUTES_KEY, cache=config
        )
        now = clock.now()
        rows = await repository.warn_due(
            session, now, now + timedelta(minutes=minutes), limit=limit
        )

        def data(row: Any) -> dict[str, Any]:
            return {"expires_at": row.expires_at.isoformat()}

        told = await _tell(session, rows, THREAD_EXPIRING, data)
        for user_id, payload in told:
            notifications_repository.add(
                session, user_id, EXPIRING_NOTIFICATION, payload
            )
    return len(rows)


async def _tell(
    session: AsyncSession,
    rows: Sequence[Any],
    type_: str,
    data: Callable[[Any], dict[str, Any]],
) -> list[tuple[UUID, dict[str, Any]]]:
    """`type_` to each of each Thread's two who sees the expiry (D-554's
    allowlist): a man. What was queued, by whom."""
    genders = await repository.genders_of(
        session, {user for row in rows for user in (row.user_low, row.user_high)}
    )
    told = []
    for row in rows:
        payload = {"thread_id": str(row.id), **data(row)}
        for user_id in (row.user_low, row.user_high):
            if rules.sees_the_expiry(genders.get(user_id)):
                events.queue(session, user_id, type_, payload)
                told.append((user_id, payload))
    return told
