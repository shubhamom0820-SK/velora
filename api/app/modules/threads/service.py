"""Opening a Thread (T-7.1); listing them (T-7.2); clearing one from your own
chats (T-7.8); its hour bought and run out (T-7.6); the knot tied and untied
(T-7.7, at the end).

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
from app.modules.kudos import service as kudos_service
from app.modules.messages import limits
from app.modules.messages import service as messages_service
from app.modules.notifications import service as notifications_service
from app.modules.notifications.rules import Kind
from app.modules.pricing import service as pricing_service
from app.modules.safety import fraud
from app.modules.safety import signals as safety_signals
from app.modules.threads import repository, rules, schemas
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType

THREAD_OPENED = "thread.opened"
# T-7.6: to whoever sees the expiry, a man, never her (D-097, D-554).
THREAD_EXPIRING = "thread.expiring"
THREAD_EXPIRED = "thread.expired"
# T-7.7: a knot requested and accepted are notifications too (T-9.4's
# `Kind`); an untie is the event alone (D-770).
KNOT_REQUESTED = "knot.requested"
KNOT_ACCEPTED = "knot.accepted"
KNOT_UNTIED = "knot.untied"


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
    # T-9.2 (D-900): more than `fraud.NEW_THREADS_MAX` opened in a day.
    opened_today = await repository.opened_since(
        session, user.id, clock.now() - fraud.NEW_THREADS_WINDOW
    )
    if opened_today > fraud.NEW_THREADS_MAX:
        await safety_signals.record_crossing(
            session, user.id, fraud.MANY_NEW_THREADS, {"threads": opened_today}
        )
    payload = {"thread_id": str(thread.id), "user_id": str(user.id)}
    events.queue(session, other_id, THREAD_OPENED, payload)
    await notifications_service.notify(session, other_id, Kind.THREAD, payload)
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
        # The opening's own notification tells her; no second push for it.
        await messages_service.announce(session, row, other_id, notify=False)
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


def _card_of(row: Any, now: datetime, settings: Settings) -> schemas.CardLite:
    """The other person from their card-lite columns: a deleted account is
    `deleted` and nothing more (D-051, D-500)."""
    deleted = row.other_status is UserStatus.DELETED
    return schemas.CardLite(
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


def _row_of(
    row: Any, user: User, now: datetime, settings: Settings
) -> schemas.ThreadRow:
    thread = view_of(row.Thread, user)
    other = _card_of(row, now, settings)
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
    session: AsyncSession, user: User, thread_id: UUID, *, settings: Settings
) -> schemas.ThreadView:
    """One of `user`'s Threads, with the other person and what `user`'s next
    message costs (T-7.11, D-870); anyone else's, or one a block stands
    across, is `NOT_FOUND`. Whether `user` may send them a gift and give them
    kudos (D-880), each by the rule its own endpoint keeps, and no profile
    view recorded."""
    async with session.begin():
        thread = await repository.my_thread(session, thread_id, user.id)
        if thread is None:
            raise _not_found()
        view = view_of(thread, user)
        other_id = view.other_user_id
        card = await repository.card_of(session, other_id)
        price = await messages_service.send_price(session, user, thread)
        gift = await discovery_service.can_gift(
            session, user, other_id, await repository.gender_of(session, other_id)
        )
        kudos = await kudos_service.state(session, user.id, other_id, thread)
    return schemas.ThreadView(
        **view.model_dump(),
        other=_card_of(card, clock.now(), settings),
        send_price=price,
        can_gift=gift,
        kudos=kudos,
    )


# --- Clearing (T-7.8) ---------------------------------------------------------------

# `(cleared_at, id)`: when the clearing reached, then the Thread.
CLEARED_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


async def list_cleared(
    session: AsyncSession, user: User, *, params: PageParams, settings: Settings
) -> schemas.ClearedThreadRowPage:
    """The chats `user` cleared that nothing newer has brought back (T-9.8,
    P-510): Threads and Knots alike, newest clearing first, never one across a
    block either way. Each is restored by `restore`."""
    after = None if params.cursor is None else CLEARED_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.cleared_rows(
            session, user.id, after=after, limit=params.fetch
        )
    keys = {row.Thread.id: row.cleared_at for row in rows}
    return schemas.ClearedThreadRowPage.of(
        _rows(rows, user, clock.now(), settings),
        params,
        lambda item: CLEARED_CURSOR.encode((keys[item.id], item.id)),
    )


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
    expiry, never her (D-097), and nobody across a block (T-9.1). How many it
    took."""
    async with session.begin():
        rows = await repository.expire_due(session, clock.now(), limit=limit)
        told = [row for row in rows if not row.blocked]
        await _tell(session, told, THREAD_EXPIRED, lambda row: {})
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
            await notifications_service.notify(
                session, user_id, Kind.THREAD_EXPIRING, payload
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


# --- The knot (T-7.7) ---------------------------------------------------------------


def _other_in(thread: Thread, user_id: UUID) -> UUID:
    return thread.user_high if user_id == thread.user_low else thread.user_low


async def _held(session: AsyncSession, viewer_id: UUID, thread_id: UUID) -> Thread:
    """One of `viewer_id`'s Threads, its row held until the transaction ends,
    so taps and untying are one after the other; anyone else's, or one across
    a block, `NOT_FOUND`."""
    thread = await repository.my_thread(session, thread_id, viewer_id, lock=True)
    if thread is None:
        raise _not_found()
    return thread


async def tie(session: AsyncSession, user: User, thread_id: UUID) -> schemas.Thread:
    """`POST /threads/{id}/knot`: `user`'s tap, free (D-003), on a live or an
    expired Thread. The second of the two makes it a Knot: no expiry, ever, and
    `knot.accepted` to both; the first asks the other (`knot.requested`). A tap
    already there, a Knot's included, is returned as it is and nobody is told
    again (D-770). Holding the Thread's row, so two taps at once are one after the
    other and the second finds the first. A deleted account is
    `ACCOUNT_DELETED`, nothing written (D-770)."""
    user_id = user.id
    async with session.begin():
        thread = await _held(session, user_id, thread_id)
        # A Knot carries both taps, so tapping one is tapping again.
        if rules.tapped(thread, user_id):
            return view_of(thread, user)
        other_id = _other_in(thread, user_id)
        if await repository.status_of(session, other_id) is UserStatus.DELETED:
            raise rules.account_deleted()
        now = clock.now()
        if user_id == thread.user_low:
            thread.low_knot_at = now
        else:
            thread.high_knot_at = now
        if rules.tied_by_both(thread):
            thread.status = ThreadStatus.KNOTTED
            thread.knotted_at = now
            thread.expires_at = None
            thread.expiry_warned_at = None
            accepted = {"thread_id": str(thread.id), "knotted_at": now.isoformat()}
            for one in (user_id, other_id):
                events.queue(session, one, KNOT_ACCEPTED, accepted)
            await notifications_service.notify(
                session,
                other_id,
                Kind.KNOT_ACCEPTED,
                {"thread_id": str(thread.id), "user_id": str(user_id)},
            )
        else:
            requested = {"thread_id": str(thread.id), "user_id": str(user_id)}
            events.queue(session, other_id, KNOT_REQUESTED, requested)
            await notifications_service.notify(
                session, other_id, Kind.KNOT_REQUESTED, requested
            )
        return view_of(thread, user)


async def untie(
    session: AsyncSession,
    user: User,
    thread_id: UUID,
    *,
    config: admin_service.ConfigCache | None = None,
) -> schemas.Thread:
    """`DELETE /threads/{id}/knot`: either of the two unties a Knot. It is
    `active` again with both taps cleared; a Thread from a match gets a fresh
    `thread_hours` from now, a private message none (D-550, D-560), and the
    other is told (`knot.untied`, no notification). A Thread that isn't a Knot
    is returned as it is, nobody told (D-770): a pending tap stays, so tapping
    again asks nobody twice."""
    user_id = user.id
    async with session.begin():
        thread = await _held(session, user_id, thread_id)
        if thread.status is not ThreadStatus.KNOTTED:
            return view_of(thread, user)
        hours = await admin_service.config_int(
            session, rules.THREAD_HOURS_KEY, cache=config
        )
        thread.status = ThreadStatus.ACTIVE
        thread.expires_at = rules.untied_until(thread.origin, clock.now(), hours)
        thread.knotted_at = None
        thread.low_knot_at = None
        thread.high_knot_at = None
        thread.expiry_warned_at = None
        events.queue(
            session,
            _other_in(thread, user_id),
            KNOT_UNTIED,
            {"thread_id": str(thread.id)},
        )
        return view_of(thread, user)
