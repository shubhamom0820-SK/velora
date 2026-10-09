"""Messages (T-7.1 writes the first; T-7.3 reads them and sends the rest;
T-7.5 marks them read and says who hears a typing).

Every text passes `filters` first: refused for abuse or asking for money
(`MESSAGE_REJECTED`, a `message_rejected` signal kept), then masked in the
Thread's first `mask_first_n_messages` (D-030). A message is written in the
transaction that makes it true, and `message.new` goes to both people, each
seeing it as theirs or not.

A voice note (T-7.9, D-620) is a woman's alone (D-010). Her browser PUTs it
to an upload key; at the send the server reads it, judges its type and
measures its length by its bytes (`core.audio`), and writes those same bytes
to the key the message keeps, which no client can write to. A man pays once
to unlock it (`voice_unlock`, D-621), and its file is reached only by a link
signed for 10 minutes, never inside a `Message`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import structlog
from pydantic import AwareDatetime, TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audio, clock, events
from app.core.config import Settings
from app.core.enums import (
    Gender,
    LedgerReason,
    MessageKind,
    ThreadOrigin,
    UserStatus,
)
from app.core.errors import AppError, invalid_field
from app.core.pagination import Cursor, PageParams
from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.storage_keys import parse_voice_upload_key, voice_key
from app.modules.admin import service as admin_service
from app.modules.messages import filters, limits, repository, rules
from app.modules.messages.models import Message as MessageRow
from app.modules.messages.schemas import (
    MediaUrl,
    Message,
    MessagePage,
    ReadRequest,
    SendMessageRequest,
)
from app.modules.notifications import service as notifications_service
from app.modules.notifications.rules import Kind
from app.modules.pricing import service as pricing_service
from app.modules.safety import fraud
from app.modules.safety import service as safety_service
from app.modules.safety import signals as safety_signals
from app.modules.threads import rules as threads_rules
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.rules import Ref, RefType

MASK_KEY = "mask_first_n_messages"
MESSAGE_NEW = "message.new"
MESSAGE_READ = "message.read"

# A voice note (T-7.9): 2 MB and 60 seconds at most, the length measured.
MAX_VOICE_BYTES = 2 * 1024 * 1024
MAX_VOICE_SECONDS = 60
MEDIA_TTL_S = 600  # D-027: a signed GET lasts 10 minutes

log = structlog.get_logger(__name__)


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
    transaction, which holds the Thread. The Thread counts it, and the fraud
    signals it may raise are written with it."""
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
    # T-9.2's signals (D-900): a contact detail masked, and the same first
    # message sent to more than `fraud.IDENTICAL_MAX` people.
    if masked.masked:
        safety_signals.record_contact_masked(session, sender_id)
    if thread.message_count == 0:
        same = await repository.same_first_messages(
            session, sender_id, text, clock.now() - fraud.IDENTICAL_WINDOW
        )
        if same > fraud.IDENTICAL_MAX:
            await safety_signals.record_crossing(
                session, sender_id, fraud.IDENTICAL_FIRST_MESSAGE, {"people": same}
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


async def announce(
    session: AsyncSession,
    row: MessageRow,
    recipient_id: UUID,
    *,
    recipient_gender: Gender | None = None,
    notify: bool = True,
) -> None:
    """`message.new` to both people, each with their own view of it. A voice
    note reaches the recipient locked unless their gender says they hear it
    free, so a caller that doesn't say never tells a man it is unlocked.

    And, unless `notify` is false, a `message` notification to the recipient
    (T-9.4): a push only, sent only while they have no socket open (D-854),
    never with the message's text in it."""
    for user_id in (row.sender_id, recipient_id):
        locked = user_id == recipient_id and rules.locked_for(
            row, user_id, recipient_gender, unlocked=False
        )
        events.queue(
            session,
            user_id,
            MESSAGE_NEW,
            {
                "thread_id": str(row.thread_id),
                "message": view_of(row, user_id, locked=locked).model_dump(mode="json"),
            },
        )
    if notify:
        await notifications_service.notify(
            session,
            recipient_id,
            Kind.MESSAGE,
            {"thread_id": str(row.thread_id), "user_id": str(row.sender_id)},
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


def unsupported_audio() -> AppError:
    """What to do, not only no (as D-089 for photos)."""
    return AppError(
        "UNSUPPORTED_AUDIO",
        f"Send a {audio.ACCEPTED_NAMES} recording.",
        status=422,
        details={"accepted": list(audio.ACCEPTED_TYPES)},
    )


def _audio_too_large() -> AppError:
    return AppError(
        "AUDIO_TOO_LARGE",
        "Voice notes can be up to 2 MB.",
        status=422,
        details={"max_bytes": MAX_VOICE_BYTES},
    )


def _audio_too_long() -> AppError:
    return AppError(
        "AUDIO_TOO_LONG",
        "Voice notes can be up to a minute long.",
        status=422,
        details={"max_seconds": MAX_VOICE_SECONDS},
    )


def _other_of(thread: Thread, user_id: UUID) -> UUID:
    return thread.user_high if thread.user_low == user_id else thread.user_low


async def _answer(
    session: AsyncSession, thread: Thread, user_id: UUID, other_id: UUID
) -> LedgerReason | None:
    """What `user_id`'s next message answers for (D-551, D-641), or None: read
    by the send and by `send_price`, so the price shown is the price charged."""
    return rules.answer_price(
        thread,
        user_id,
        wrote=await repository.has_written(session, thread.id, user_id),
        they_wrote=await repository.has_written(session, thread.id, other_id),
        bought_time=await repository.has_paid(
            session, thread.id, user_id, rules.TIME_BOUGHT
        ),
    )


async def send_price(session: AsyncSession, user: User, thread: Thread) -> int:
    """What `user`'s next text message in `thread` costs now, in Velas (T-7.11,
    D-870): the answer's price, or a private message's, as the send charges
    them; 0 for a woman, whom `pricing` charges nothing (D-098). The web shows
    it and sends it back as `shown_price` (P-56). An expired Thread refuses his
    send whatever this says (D-097)."""
    price = 0
    answer = await _answer(session, thread, user.id, _other_of(thread, user.id))
    if answer is not None:
        price += await pricing_service.price_for(session, user, answer)
    if rules.private_message_priced(thread):
        price += await pricing_service.price_for(session, user, LedgerReason.DM_MESSAGE)
    return price


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


@dataclass(frozen=True)
class _Voice:
    """A voice note's upload, checked: the message's id, where its bytes now
    are, and their length in whole seconds."""

    message_id: UUID
    upload_key: str
    media_key: str
    duration_s: int


async def check_voice(
    storage: StorageProvider, settings: Settings, thread_id: UUID, upload_key: str
) -> _Voice:
    """Read the upload, judge it by its bytes, and keep those bytes (D-620).

    In order: the key is one this Thread's upload URL gave, else
    `VALIDATION_ERROR`; something is there, else the same; 2 MB at most, by
    its size before a byte is read (a presigned PUT can't cap it); the bytes
    are the type the URL was signed for; its length is told and 60 seconds at
    most. The bytes measured are written to a key of their own, new each time,
    where no client can write: a PUT again to the upload URL, or the same
    upload sent twice, never changes a file a message keeps.
    """
    parsed = parse_voice_upload_key(upload_key)
    if parsed is None or parsed.thread_id != thread_id:
        raise invalid_field("media_key", "is not one this Thread's upload URL gave")
    bucket = settings.R2_BUCKET_PRIVATE
    try:
        info = await storage.head(bucket, upload_key)
        if info.size > MAX_VOICE_BYTES:
            raise _audio_too_large()
        data = await storage.get_bytes(bucket, upload_key)
    except ObjectNotFound:
        raise invalid_field("media_key", "has nothing uploaded to it") from None
    # Read once: what was measured is what is kept, so the size is the bytes'.
    if len(data) > MAX_VOICE_BYTES:
        raise _audio_too_large()
    if audio.sniff(data[: audio.SNIFF_BYTES]) != parsed.kind:
        raise unsupported_audio()
    try:
        seconds = audio.whole_seconds(audio.duration(data, parsed.kind))
    except audio.UnreadableAudio:
        raise unsupported_audio() from None
    if seconds > MAX_VOICE_SECONDS:
        raise _audio_too_long()
    media_key = voice_key(thread_id, uuid4(), parsed.kind)
    await storage.put_bytes(bucket, media_key, data, parsed.kind)
    return _Voice(parsed.message_id, upload_key, media_key, seconds)


async def send(
    session: AsyncSession,
    redis: Redis,
    user: User,
    thread_id: UUID,
    request: SendMessageRequest,
    *,
    storage: StorageProvider,
    settings: Settings,
    config: admin_service.ConfigCache | None = None,
) -> Message:
    """`request` sent in the Thread, by one of its two (T-7.3).

    In order: a voice note is a woman's alone (D-010); a text passes the
    filters; the same `client_msg_id` again returns the message it made, with
    nothing charged; nothing reaches a deleted account; an expired Thread
    refuses him and takes hers (D-097), by the clock (D-560); he pays what
    D-098 and D-250 say (`rules.answer_price`, nothing after a re-open or an
    Extend he paid for, D-641, and `dm_message` in a private message); her
    message moves the hour on, his never does (D-097's amendment); masked
    while the Thread is young (D-030); both told. A voice note's upload is
    checked once the Thread is known to be hers (`check_voice`), outside any
    transaction: no lock waits on storage.
    """
    # Read now: a refusal rolls the session back, which expires `user`.
    user_id, gender = user.id, user.gender
    day = clock.today_ist()
    if request.kind is MessageKind.VOICE:
        if not rules.may_send_voice(gender):
            raise _not_allowed()
    else:
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
    voice = None
    if request.media_key is not None:
        voice = await check_voice(storage, settings, thread_id, request.media_key)
    taken = limits.Taken(redis, user_id, day)
    try:
        if new_men is not None:
            await taken.new_man(other_id, new_men)
        if private is not None:
            await taken.private_message(private)
        async with session.begin():
            sent = await _send_in(
                session, user, thread_id, other_id, request, voice, config=config
            )
    except BaseException:
        await taken.give_back()
        raise
    if not sent.new:
        await taken.give_back()
    if voice is not None and sent.new:
        await _drop_upload(storage, settings, voice.upload_key)
    return sent.message


async def _drop_upload(
    storage: StorageProvider, settings: Settings, upload_key: str
) -> None:
    """The upload, once its bytes are the message's: never needed again. Its
    failing loses nothing (the message is sent), so it is logged, not raised;
    what it leaves behind is P-521's."""
    try:
        await storage.delete(settings.R2_BUCKET_PRIVATE, upload_key)
    except Exception:  # the send already succeeded
        log.warning("voice_upload_not_deleted", exc_info=True)


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
    voice: _Voice | None,
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
    answer = await _answer(session, thread, user.id, other_id)
    if answer is not None:
        await pricing_service.charge(
            session,
            user,
            answer,
            shown=request.shown_price,
            ref=Ref(RefType.THREAD, thread.id),
            event=rules.answer_event(thread.id)
            if answer is LedgerReason.THREAD_REOPEN
            else None,
        )
    if voice is not None:
        row = await _write_voice(session, thread, user.id, voice, request)
    else:
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
            session,
            user,
            LedgerReason.DM_MESSAGE,
            shown=request.shown_price,
            ref=Ref(RefType.MESSAGE, row.id),
        )
    if not expired and threads_rules.restarts_the_hour(thread, user.gender):
        hours = await admin_service.config_int(
            session, threads_rules.THREAD_HOURS_KEY, cache=config
        )
        later = now + timedelta(hours=hours)
        if thread.expires_at is None or later > thread.expires_at:
            thread.expires_at = later
            thread.expiry_warned_at = None
    await announce(
        session,
        row,
        other_id,
        recipient_gender=await repository.gender_of(session, other_id),
    )
    return _Sent(view_of(row, user.id), new=True)


async def _write_voice(
    session: AsyncSession,
    thread: Thread,
    sender_id: UUID,
    voice: _Voice,
    request: SendMessageRequest,
) -> MessageRow:
    """The voice note in `thread`, under the id its upload URL gave, in the
    caller's transaction, which holds the Thread: so one upload is one
    message, and sent again under another `client_msg_id` is refused."""
    if await repository.message_exists(session, voice.message_id):
        raise AppError(
            "ALREADY_EXISTS", "That voice note was already sent.", status=409
        )
    row = await repository.add_voice(
        session,
        message_id=voice.message_id,
        thread_id=thread.id,
        sender_id=sender_id,
        media_key=voice.media_key,
        duration_s=voice.duration_s,
        client_msg_id=request.client_msg_id,
    )
    thread.message_count += 1
    thread.last_message_at = row.created_at
    return row


# --- Read receipts and typing (T-7.5) -----------------------------------------------

# `read_at` in the event as `Message.read_at` is in a response.
_AS_JSON: TypeAdapter[datetime] = TypeAdapter(datetime)


async def mark_read(
    session: AsyncSession, user: User, thread_id: UUID, request: ReadRequest
) -> None:
    """The other person's messages read by `user`, up to the one named.

    The message named must be one `user` can see: in this Thread, after their
    clearing. Only the other person's, only those not read yet, and only those
    after the clearing (a message hidden from them was never seen): a read_at
    once set never moves. `message.read` goes to the other person alone, naming
    the newest message it marked, and only if it marked one. It carries no
    countdown and no price, whoever reads (D-554). Anyone else's Thread, or one
    across a block, is `NOT_FOUND`, and so is a message they can't see.
    """
    user_id = user.id
    async with session.begin():
        thread = await repository.thread_of(session, thread_id, user_id)
        if thread is None:
            raise _not_found()
        since = await repository.cleared_at(session, thread_id, user_id)
        target = await repository.message_in(
            session, thread_id, request.up_to_message_id
        )
        if target is None or (since is not None and target.created_at <= since):
            raise _not_found()
        at = clock.now()
        marked = await repository.mark_read(
            session,
            thread_id,
            user_id,
            up_to=(target.created_at, target.id),
            since=since,
            at=at,
        )
        if not marked:
            return
        _, newest = max(marked)
        events.queue(
            session,
            _other_of(thread, user_id),
            MESSAGE_READ,
            {
                "thread_id": str(thread_id),
                "up_to_message_id": str(newest),
                "read_at": _AS_JSON.dump_python(at, mode="json"),
            },
        )


async def typing_recipient(
    session: AsyncSession, user_id: UUID, thread_id: UUID
) -> UUID | None:
    """Who hears that `user_id` is typing in the Thread: the other person, if
    `user_id` is one of its two and no block stands between them; else nobody."""
    async with session.begin():
        thread = await repository.thread_of(session, thread_id, user_id)
    return None if thread is None else _other_of(thread, user_id)


# --- A voice note's file (T-7.9) -----------------------------------------------------


async def unlock(
    session: AsyncSession,
    user: User,
    message_id: UUID,
    *,
    shown: int,
    storage: StorageProvider,
    settings: Settings,
) -> MediaUrl:
    """`POST /messages/{id}/unlock`: a man pays once to hear the voice note
    (D-010, D-621), then has its link.

    Not a voice note in a Thread of theirs, or across a block: `NOT_FOUND`.
    Locked for them (`rules.locked_for`): the unlock is recorded and
    `voice_unlock` charged at the price shown (P-56) in one transaction, so a
    refusal writes neither. Already unlocked, or never locked (its sender, a
    woman): the link, nothing charged. An expired Thread is no bar: unlocking
    isn't a send (D-097).
    """
    user_id, gender = user.id, user.gender
    async with session.begin():
        row = await repository.voice_of(session, message_id, user_id)
        if row is None or row.media_key is None:
            raise _not_found()
        media_key = row.media_key
        # Recorded first: a second unlock at once waits on this row, finds
        # it, and charges nothing.
        if rules.locked_for(
            row, user_id, gender, unlocked=False
        ) and await repository.add_unlock(session, user_id, row.id):
            await pricing_service.charge(
                session,
                user,
                LedgerReason.VOICE_UNLOCK,
                shown=shown,
                ref=Ref(RefType.MESSAGE, row.id),
            )
    return await _signed(storage, settings, media_key)


async def media(
    session: AsyncSession,
    user: User,
    message_id: UUID,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> MediaUrl:
    """`GET /messages/{id}/media`: the voice note's link, for its sender and
    anyone it isn't locked for; locked, `NOT_ALLOWED` (unlock it first)."""
    async with session.begin():
        row = await repository.voice_of(session, message_id, user.id)
        if row is None or row.media_key is None:
            raise _not_found()
        unlocked = await repository.has_unlocked(session, user.id, row.id)
        if rules.locked_for(row, user.id, user.gender, unlocked):
            raise AppError(
                "NOT_ALLOWED", "Unlock this voice note to hear it.", status=422
            )
        media_key = row.media_key
    return await _signed(storage, settings, media_key)


async def _signed(
    storage: StorageProvider, settings: Settings, media_key: str
) -> MediaUrl:
    url = await storage.presign_get(
        settings.R2_BUCKET_PRIVATE, media_key, ttl=MEDIA_TTL_S
    )
    return MediaUrl(url=url)
