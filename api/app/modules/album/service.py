"""The private album (T-8.4): asking to see someone's private photos, her
answer, and the copies watermarked for the one she let see them.

**Asking** (`POST /album-requests`), one transaction under the requester's
lock, so two requests at once are one after the other:

1. Someone he can't reach as a private message can (D-550's reach), himself
   among them, is `NOT_FOUND`, the same answer as an id nobody holds, so a
   block is never revealed (D-493).
2. A pending or granted request to her already: that one, nothing charged.
3. **The cooldown** (D-731): within `album_reask_days` (30, read fresh) of her
   declining or revoking one of his requests, `NOT_ALLOWED`
   (`recently_declined`).
4. **Nothing to see:** no approved private photo with a scored copy (D-700),
   `NOT_ALLOWED` (`empty_album`), so nobody pays for an empty album.
5. The request, then `pricing.service.charge()`: the `album_request` row's
   price, 1 Vela for a man and nothing for a woman (D-231, D-098), refused
   with `PRICE_CHANGED` unless it is the price he was shown (P-56, D-600). A
   refusal rolls back the request with it.

Every refusal comes before anything is charged or written.

**Her answer:** a grant queues `watermark_album`; a decline returns nothing
(D-230), and `refund_album_declined` stays unused. Either is told to him as
`album.decided`. A revoke closes it and queues the copies' deletion. A decline
and a revoke each start the cooldown, from `decided_at`, which is the time of
her last answer to it (D-731).

**The album** (`GET /users/{id}/album`): only to him while she can still be
opened by him (D-493), and only his own copies, each signed for 10 minutes.
A photo approved before D-700 has no scored copy and is never shown.

**The copies** (`sync_copies`, the `watermark_album` job): rendered from each
photo's `scored_key`, never `raw_key` (D-700), with his `@username` tiled over
it; written to a key of the request's own (D-730), and recorded only while the
request is still granted, so a copy rendered as she revokes is deleted, never
kept. Deleted when the request is no longer granted, or the photo no longer
shown: each file first, read back as gone, then its row.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events, images
from app.core.config import Settings
from app.core.enums import AlbumRequestStatus, LedgerReason, UserStatus
from app.core.pagination import Cursor, PageParams
from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.queue import WATERMARK_ALBUM, Queue
from app.core.storage_keys import album_key, public_url
from app.modules.admin import service as admin_service
from app.modules.album import repository, rules, schemas
from app.modules.album.models import AlbumRequest
from app.modules.discovery import rules as discovery_rules
from app.modules.discovery import service as discovery_service
from app.modules.notifications import service as notifications_service
from app.modules.notifications.rules import Kind
from app.modules.pricing import service as pricing_service
from app.modules.threads.schemas import CardLite
from app.modules.users.models import User
from app.modules.wallet.rules import Ref, RefType

log = structlog.get_logger(__name__)

ALBUM_DECIDED = "album.decided"
# T-9.4 (P-631): a new request, to her, at its commit; D-732 had none.
ALBUM_REQUESTED = "album.requested"

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


# --- Asking ----------------------------------------------------------------------------


async def ask(
    session: AsyncSession,
    user: User,
    body: schemas.CreateAlbumRequest,
    *,
    settings: Settings,
) -> schemas.AlbumRequest:
    async with session.begin():
        row = await _ask_in(session, user, body)
        return await _view(session, row, settings)


async def _ask_in(
    session: AsyncSession, user: User, body: schemas.CreateAlbumRequest
) -> AlbumRequest:
    await repository.lock_requester(session, user.id)
    owner_id = body.owner_id
    if owner_id == user.id or not await discovery_service.can_reach(
        session, user, owner_id, mutual=True
    ):
        raise rules.not_found()
    existing = await repository.live_request(session, user.id, owner_id)
    if existing is not None:
        return existing

    now = clock.now()
    days = await admin_service.config_int(session, rules.REASK_KEY)
    closed_at = await repository.last_closed_at(session, user.id, owner_id)
    if not rules.may_ask_again(closed_at, now, days):
        raise rules.recently_declined()
    if await repository.albumable_count(session, owner_id) == 0:
        raise rules.empty_album()

    row = await repository.add(session, requester_id=user.id, owner_id=owner_id, at=now)
    paid = await pricing_service.charge(
        session,
        user,
        LedgerReason.ALBUM_REQUEST,
        shown=body.shown_price,
        ref=Ref(RefType.ALBUM_REQUEST, row.id),
    )
    row.credits_charged = 0 if paid is None else -paid.entry.delta
    told = {"album_request_id": str(row.id), "user_id": str(user.id)}
    events.queue(session, owner_id, ALBUM_REQUESTED, told)
    await notifications_service.notify(session, owner_id, Kind.ALBUM_REQUEST, told)
    return row


# --- Her list, and her answer ------------------------------------------------------------

# `(created_at, id)`, newest first.
INCOMING_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


async def incoming(
    session: AsyncSession, user: User, *, params: PageParams, settings: Settings
) -> schemas.AlbumRequestPage:
    """`GET /album-requests/incoming`: her pending and granted requests, newest
    first, none from across a block."""
    after = None if params.cursor is None else INCOMING_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.incoming(
            session, user.id, after=after, limit=params.fetch
        )
    now = clock.now()
    return schemas.AlbumRequestPage.of(
        [_of_row(row, now, settings) for row in rows],
        params,
        lambda item: INCOMING_CURSOR.encode((item.created_at, item.id)),
    )


async def decide(
    session: AsyncSession,
    user: User,
    request_id: UUID,
    grant: bool,
    *,
    queue: Queue,
    settings: Settings,
) -> schemas.AlbumRequest:
    """Her answer to a pending request of hers. The same answer again changes
    nothing; the other one, once answered, is `NOT_ALLOWED`."""
    wanted = AlbumRequestStatus.GRANTED if grant else AlbumRequestStatus.DECLINED
    granted_now = False
    async with session.begin():
        row = await repository.request_for_update(session, request_id, owner_id=user.id)
        if row is None:
            raise rules.not_found()
        if row.status is AlbumRequestStatus.PENDING:
            row.status = wanted
            row.decided_at = clock.now()
            granted_now = grant
            decided = {
                "album_request_id": str(row.id),
                "user_id": str(user.id),
                "granted": grant,
            }
            events.queue(session, row.requester_id, ALBUM_DECIDED, decided)
            await notifications_service.notify(
                session, row.requester_id, Kind.ALBUM_DECIDED, decided
            )
        elif row.status is not wanted:
            raise rules.already_decided()
        view = await _view(session, row, settings)
    if granted_now:
        await queue.enqueue(
            WATERMARK_ALBUM,
            job_id=rules.grant_job_id(request_id),
            request_id=str(request_id),
        )
    return view


async def revoke(
    session: AsyncSession, user: User, request_id: UUID, *, queue: Queue
) -> None:
    """She takes a grant back: the request is `revoked`, and its copies are
    deleted by `watermark_album`. Revoking twice is the same as once."""
    async with session.begin():
        row = await repository.request_for_update(session, request_id, owner_id=user.id)
        if row is None:
            raise rules.not_found()
        if row.status is AlbumRequestStatus.REVOKED:
            return
        if row.status is not AlbumRequestStatus.GRANTED:
            raise rules.not_granted()
        row.status = AlbumRequestStatus.REVOKED
        # Her last answer to it: the cooldown runs from here (D-731).
        row.decided_at = clock.now()
    await queue.enqueue(
        WATERMARK_ALBUM,
        job_id=rules.revoke_job_id(request_id),
        request_id=str(request_id),
    )


# --- The album ---------------------------------------------------------------------------


async def album(
    session: AsyncSession,
    user: User,
    owner_id: UUID,
    *,
    storage: StorageProvider,
    queue: Queue,
    settings: Settings,
) -> schemas.Album:
    """`GET /users/{id}/album`: his latest request to her, and, while it is
    granted, a link to each of his copies of the photos it shows."""
    async with session.begin():
        if owner_id == user.id or not await discovery_service.can_reach(
            session, user, owner_id, mutual=False
        ):
            raise rules.not_found()
        latest = await repository.latest_request(session, user.id, owner_id)
        if latest is None or latest.status is not AlbumRequestStatus.GRANTED:
            return schemas.Album(
                status=None if latest is None else latest.status, photos=[]
            )
        keys = await repository.shown_copies(session, latest.id, owner_id)
        photos = await repository.albumable_photos(session, owner_id)
        copied = {c.photo_id for c in await repository.copies(session, latest.id)}
        missing = [photo.id for photo in photos if photo.id not in copied]
    if missing:
        # Added after the grant, or its rendering failed: made now, shown on a
        # later look.
        await queue.enqueue(
            WATERMARK_ALBUM,
            job_id=rules.photo_job_id(latest.id, min(missing)),
            request_id=str(latest.id),
        )
    urls = [
        await storage.presign_get(settings.R2_BUCKET_PRIVATE, key, ttl=rules.LINK_TTL_S)
        for key in keys
    ]
    return schemas.Album(
        status=AlbumRequestStatus.GRANTED,
        photos=[schemas.AlbumPhoto(url=url) for url in urls],
    )


# --- Views ---------------------------------------------------------------------------------


async def _view(
    session: AsyncSession, row: AlbumRequest, settings: Settings
) -> schemas.AlbumRequest:
    [found] = await repository.requester_columns(session, [row.id])
    return _of_row(found, clock.now(), settings)


def _of_row(row: Any, now: datetime, settings: Settings) -> schemas.AlbumRequest:
    request: AlbumRequest = row.AlbumRequest
    return schemas.AlbumRequest(
        id=request.id,
        requester=_requester_card(row, now, settings),
        owner_id=request.owner_id,
        status=request.status,
        created_at=request.created_at,
        decided_at=request.decided_at,
    )


def _requester_card(row: Any, now: datetime, settings: Settings) -> CardLite:
    """The requester as a card, as a Thread's row shows the other person: a
    deleted account has no name, username or photo (D-051, D-500)."""
    deleted = row.requester_status is UserStatus.DELETED
    return CardLite(
        id=row.AlbumRequest.requester_id,
        first_name=None if deleted else row.requester_first_name,
        username=None if deleted else row.requester_username,
        main_photo_url=None
        if deleted or row.requester_photo_key is None
        else public_url(settings, row.requester_photo_key),
        shows_badge=not deleted and bool(row.requester_badge),
        is_online=not deleted
        and row.requester_last_active_at is not None
        and row.requester_last_active_at >= now - discovery_rules.ONLINE_FOR,
        deleted=deleted,
    )


# --- The copies (the `watermark_album` job) -------------------------------------------


class TryAgain(Exception):
    """Storage failed for now. `watermark_album` tries again; the last try
    logs `event` at error level."""

    def __init__(self, event: str, what: str) -> None:
        super().__init__(what)
        self.event = event


async def sync_copies(
    sessions: Sessions,
    request_id: UUID,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> str:
    """Bring one request's copies in line with it: while it is granted, a copy
    of each photo the album shows and none of any other; otherwise none. What
    it did, for the job's result."""
    bucket = settings.R2_BUCKET_PRIVATE
    async with sessions() as session, session.begin():
        request = await session.get(AlbumRequest, request_id)
        if request is None:
            return "no such request"
        granted = request.status is AlbumRequestStatus.GRANTED
        photos = (
            await repository.albumable_photos(session, request.owner_id)
            if granted
            else []
        )
        copies = await repository.copies(session, request_id)
        username = await repository.username_of(session, request.requester_id)
    shown = {photo.id for photo in photos}
    stale = [copy for copy in copies if copy.photo_id not in shown]
    for copy in stale:
        await _delete_file(storage, bucket, copy.file_key)
        async with sessions() as session, session.begin():
            await repository.delete_copy(session, copy.id)
    if not granted:
        return f"deleted {len(stale)}"

    copied = {copy.photo_id for copy in copies}
    to_make = [photo for photo in photos if photo.id not in copied]
    if to_make and not username:
        return "the viewer has no username: nothing made"
    made = 0
    for photo in to_make:
        made += await _make_copy(
            sessions,
            request_id,
            photo.id,
            photo.scored_key,
            username or "",
            storage,
            bucket,
        )
    return f"made {made}, deleted {len(stale)}"


async def _make_copy(
    sessions: Sessions,
    request_id: UUID,
    photo_id: UUID,
    scored_key: str | None,
    username: str,
    storage: StorageProvider,
    bucket: str,
) -> int:
    """One copy rendered from the scored bytes, never the upload (D-700), and
    recorded only if the request is still granted and the photo still shown
    once it is written; otherwise the file just written is deleted."""
    assert scored_key is not None
    try:
        data = await storage.get_bytes(bucket, scored_key)
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise TryAgain("album.read_failed", type(error).__name__) from None
    try:
        marked = images.watermark(data, f"@{username}")
    except images.UnreadableImage:
        log.error("album.unreadable_scored_copy", photo_id=str(photo_id))
        return 0
    key = album_key(request_id, photo_id)
    await _stored(storage.put_bytes(bucket, key, marked, "image/jpeg"))
    async with sessions() as session, session.begin():
        locked = await repository.request_for_update(session, request_id)
        still_shown = locked is not None and photo_id in {
            photo.id
            for photo in await repository.albumable_photos(session, locked.owner_id)
        }
        if (
            locked is not None
            and locked.status is AlbumRequestStatus.GRANTED
            and still_shown
        ):
            await repository.add_copy(session, locked, photo_id, key)
            return 1
    await _delete_file(storage, bucket, key)
    return 0


async def _delete_file(storage: StorageProvider, bucket: str, key: str) -> None:
    """Delete one copy and read it back as gone: a delete that answers success
    isn't proof the object left (D-090's rule)."""
    try:
        await storage.delete(bucket, key)
    except Exception:  # noqa: BLE001, S110 — the read-back below decides
        pass
    try:
        await storage.head(bucket, key)
    except ObjectNotFound:
        return
    except Exception as error:  # noqa: BLE001 — unreadable is not proof it left
        raise TryAgain("album.delete_unconfirmed", type(error).__name__) from None
    raise TryAgain("album.delete_unconfirmed", "a copy is still stored")


async def _stored(write: Awaitable[None]) -> None:
    try:
        await write
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise TryAgain("album.write_failed", type(error).__name__) from None
