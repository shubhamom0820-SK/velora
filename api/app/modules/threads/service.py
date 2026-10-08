"""Opening a Thread (T-7.1).

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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.config import Settings
from app.core.enums import MessageKind, ThreadOrigin, ThreadStatus, UserStatus
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
from app.modules.wallet.rules import Ref, RefType

THREAD_OPENED = "thread.opened"
THREAD_NOTIFICATION = "thread"


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def thread_expired() -> AppError:
    """His alone (D-097): an expired Thread lets her through."""
    return AppError(
        "THREAD_EXPIRED",
        "This Thread has run out. Re-open it to reply.",
        status=410,
    )


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
        if existing.status is ThreadStatus.EXPIRED and not (
            rules.passes_an_expired_thread(user.gender)
        ):
            raise thread_expired()
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
        session, user, rules.OPEN_PRICE[origin], ref=Ref(RefType.THREAD, thread.id)
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
