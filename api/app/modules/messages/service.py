"""Messages (T-7.1 writes the first; T-7.3 reads them and sends the rest).

Every text passes `filters` first: refused for abuse or asking for money
(`MESSAGE_REJECTED`, a `message_rejected` signal kept), then masked in the
Thread's first `mask_first_n_messages` (D-030). A message is written in the
transaction that makes it true, and `message.new` goes to both people, each
seeing it as theirs or not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import AwareDatetime
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.enums import LedgerReason, MessageKind, ThreadOrigin, UserStatus
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.modules.admin import service as admin_service
from app.modules.messages import filters, limits, repository, rules
from app.modules.messages.models import Message as MessageRow
from app.modules.messages.schemas import Message, MessagePage, SendMessageRequest
from app.modules.pricing import service as pricing_service
from app.modules.safety import service as safety_service
from app.modules.threads import rules as threads_rules
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.rules import Ref, RefType

MASK_KEY = "mask_first_n_messages"
MESSAGE_NEW = "message.new"


def _rejected(rule: str) -> AppError:
    return AppError(
        "MESSAGE_REJECTED",
        "That message can't be sent.",
        status=422,
        details={"rule": rule},
    )


async def refuse_if_rejected(session: AsyncSession, user_id: UUID, text: str) -> None:
    """Refuse `text` if it breaks a rule, keeping the signal: in a transaction
    of its own, before the send's, so the refusal can't roll it back."""
    rule = filters.refusal(text)
    if rule is None:
        return
    async with session.begin():
        safety_service.record_message_rejected(session, user_id, rule=rule)
    raise _rejected(rule)


async def write_text(
    session: AsyncSession,
    thread: Thread,
    sender_id: UUID,
    text: str,
    client_msg_id: UUID,
    *,
    mask_first_n: int,
) -> MessageRow:
    """`text` in `thread`, masked while the Thread is young, in the caller's
    transaction, which holds the Thread. The Thread counts it."""
    masked = (
        filters.mask(text)
        if thread.message_count < mask_first_n
        else filters.Masked(body=text, masked=False)
    )
    row = await repository.add_text(
        session,
        thread_id=thread.id,
        sender_id=sender_id,
        body=masked.body,
        body_raw=text if masked.masked else None,
        masked=masked.masked,
        client_msg_id=client_msg_id,
    )
    thread.message_count += 1
    thread.last_message_at = row.created_at
    return row


def view_of(
    row: MessageRow,
    viewer_id: UUID,
    *,
    from_deleted_account: bool = False,
    locked: bool = False,
) -> Message:
    """`row` as `viewer_id` sees it. Never `body_raw`."""
    mine = row.sender_id == viewer_id
    return Message(
        id=row.id,
        thread_id=row.thread_id,
        kind=row.kind,
        body=row.body,
        masked=row.masked,
        duration_s=row.duration_s,
        mine=mine,
        from_deleted_account=from_deleted_account,
        locked=locked,
        read_at=row.read_at,
        created_at=row.created_at,
        client_msg_id=row.client_msg_id if mine else None,
    )


def announce(session: AsyncSession, row: MessageRow, recipient_id: UUID) -> None:
    """`message.new` to both people, each with their own view of it."""
    for user_id in (row.sender_id, recipient_id):
        events.queue(
            session,
            user_id,
            MESSAGE_NEW,
            {
                "thread_id": str(row.thread_id),
                "message": view_of(row, user_id).model_dump(mode="json"),
            },
        )


# --- Reading and sending (T-7.3) ----------------------------------------------------

# `(created_at, id)`, newest first.
MESSAGE_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def _account_deleted() -> AppError:
    """D-500: they deleted their account; their messages stay, and nothing
    more reaches them (D-555)."""
    return AppError("ACCOUNT_DELETED", "They deleted their account.", status=410)


def _not_allowed() -> AppError:
    return AppError("NOT_ALLOWED", "That can't be sent here.", status=422)


def _other_of(thread: Thread, user_id: UUID) -> UUID:
    return thread.user_high if thread.user_low == user_id else thread.user_low


async def list_messages(
    session: AsyncSession, user: User, thread_id: UUID, params: PageParams
) -> MessagePage:
    """The Thread's messages as `user` sees them, newest first, only those
    after their clearing (D-006). Anyone else's Thread, or one across a block,
    is `NOT_FOUND`."""
    after = None if params.cursor is None else MESSAGE_CURSOR.decode(params.cursor)
    async with session.begin():
        thread = await repository.thread_of(session, thread_id, user.id)
        if thread is None:
            raise _not_found()
        since = await repository.cleared_at(session, thread_id, user.id)
        rows = await repository.page(
            session, thread_id, user.id, since=since, after=after, limit=params.fetch
        )
    items = [
        view_of(
            row.Message,
            user.id,
            from_deleted_account=bool(row.from_deleted_account),
            locked=rules.locked_for(row.Message, user.id, user.gender, row.unlocked),
        )
        for row in rows
    ]
    return MessagePage.of(
        items, params, lambda item: MESSAGE_CURSOR.encode((item.created_at, item.id))
    )


@dataclass(frozen=True)
class _Sent:
    message: Message
    new: bool


async def send(
    session: AsyncSession,
    redis: Redis,
    user: User,
    thread_id: UUID,
    request: SendMessageRequest,
    *,
    config: admin_service.ConfigCache | None = None,
) -> Message:
    """`request` sent in the Thread, by one of its two (T-7.3).

    In order: a voice note isn't sendable here (T-7.9); the text passes the
    filters; the same `client_msg_id` again returns the message it made, with
    nothing charged; nothing reaches a deleted account; an expired Thread
    refuses him and takes hers (D-097), by the clock (D-560); he pays what
    D-098 and D-250 say (`rules.answer_price`, and `dm_message` in a private
    message); her message moves the hour on, his never does (D-097's
    amendment); masked while the Thread is young (D-030); both told.
    """
    # Read now: a refusal rolls the session back, which expires `user`.
    user_id, gender = user.id, user.gender
    day = clock.today_ist()
    if request.kind is not MessageKind.TEXT:
        raise _not_allowed()
    assert request.body is not None
    await refuse_if_rejected(session, user_id, request.body)
    new_men = private = None
    async with session.begin():
        thread = await repository.thread_of(session, thread_id, user_id)
        if thread is None:
            raise _not_found()
        existing = await repository.by_client_id(
            session, user_id, request.client_msg_id
        )
        if existing is not None:
            return _again(existing, thread_id, user_id)
        other_id = _other_of(thread, user_id)
        if await repository.status_of(session, other_id) is UserStatus.DELETED:
            raise _account_deleted()
        if limits.limited(gender):
            if thread.message_count == 0 and limits.counts_as_a_man(
                await repository.gender_of(session, other_id)
            ):
                new_men = await admin_service.config_int(
                    session, limits.NEW_MEN_KEY, cache=config
                )
            if thread.origin is ThreadOrigin.DM:
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
            sent = await _send_in(
                session, user, thread_id, other_id, request, config=config
            )
    except BaseException:
        await taken.give_back()
        raise
    if not sent.new:
        await taken.give_back()
    return sent.message


def _again(existing: MessageRow, thread_id: UUID, user_id: UUID) -> Message:
    """A retried send: the message it made, if it was made in this Thread."""
    if existing.thread_id != thread_id:
        raise AppError(
            "ALREADY_EXISTS", "That message id was used elsewhere.", status=409
        )
    return view_of(existing, user_id)


async def _send_in(
    session: AsyncSession,
    user: User,
    thread_id: UUID,
    other_id: UUID,
    request: SendMessageRequest,
    *,
    config: admin_service.ConfigCache | None,
) -> _Sent:
    """The send, in the caller's transaction, holding the Thread."""
    thread = await repository.thread_of(session, thread_id, user.id, lock=True)
    if thread is None:
        raise _not_found()
    existing = await repository.by_client_id(session, user.id, request.client_msg_id)
    if existing is not None:
        return _Sent(_again(existing, thread_id, user.id), new=False)
    now = clock.now()
    expired = threads_rules.has_expired(thread, now)
    if expired and not threads_rules.passes_an_expired_thread(user.gender):
        raise threads_rules.thread_expired()
    answer = rules.answer_price(
        thread,
        user.id,
        wrote=await repository.has_written(session, thread.id, user.id),
        they_wrote=await repository.has_written(session, thread.id, other_id),
    )
    if answer is not None:
        await pricing_service.charge(
            session,
            user,
            answer,
            ref=Ref(RefType.THREAD, thread.id),
            event=rules.answer_event(thread.id)
            if answer is LedgerReason.THREAD_REOPEN
            else None,
        )
    mask_first_n = await admin_service.config_int(session, MASK_KEY, cache=config)
    assert request.body is not None
    row = await write_text(
        session,
        thread,
        user.id,
        request.body,
        request.client_msg_id,
        mask_first_n=mask_first_n,
    )
    if rules.private_message_priced(thread):
        await pricing_service.charge(
            session, user, LedgerReason.DM_MESSAGE, ref=Ref(RefType.MESSAGE, row.id)
        )
    if not expired and threads_rules.restarts_the_hour(thread, user.gender):
        hours = await admin_service.config_int(
            session, threads_rules.THREAD_HOURS_KEY, cache=config
        )
        later = now + timedelta(hours=hours)
        if thread.expires_at is None or later > thread.expires_at:
            thread.expires_at = later
            thread.expiry_warned_at = None
    announce(session, row, other_id)
    return _Sent(view_of(row, user.id), new=True)
