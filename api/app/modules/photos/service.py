"""Uploading a photo (T-4.2): a presigned PUT, then `complete`.

The browser uploads straight to the private bucket (D-027); the server never
handles the bytes on the way in. `complete` then checks what arrived: that it
exists, its size, and what it is by its first bytes, never by the type the
browser declared (D-089). An accepted public, private or face photo is queued
for moderation (T-4.4); a selfie waits for its verification's submit (T-4.5).

Public and private photos and the face photo are D-068's `photos` step, the
selfie its `selfie` step: each works at its step or after, never before.

**The face photo** (`kind` `verification`, D-391, T-4.12) is the one the selfie
is compared with: one live per person, private unless its owner chooses to show
it, which `show_face_photo` does by making an ordinary public photo from its
scored bytes. It can't change once the selfie matched, nor while one is being
compared: the match would be left pointing at a photo that is gone.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, images
from app.core.config import Settings
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.errors import AppError, invalid_field
from app.core.images import (
    ACCEPTED_NAMES,
    ACCEPTED_TYPES,
    SNIFF_BYTES,
    sniff,
)
from app.core.providers.moderation import (
    MINOR_MODEL,
    ModerationFailed,
    ModerationProvider,
    Scores,
)
from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.queue import MATCH_PHOTO, MODERATE_PHOTO, Queue
from app.core.storage_keys import public_photo_key, public_url, raw_key
from app.modules.photos import moderation as moderation_rules
from app.modules.photos import repository
from app.modules.photos.models import Photo
from app.modules.photos.schemas import Photo as PhotoOut
from app.modules.photos.schemas import UploadUrl
from app.modules.safety import service as safety_service
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.verification import repository as verification_repository

UPLOAD_TTL_S = 300  # D-027: a presigned PUT lasts 5 minutes
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PRIVATE = 6
# A pending photo is abandoned once its URL has expired, a minute's grace given,
# and nothing was ever uploaded: its place is free again.
ABANDONED_AFTER = timedelta(seconds=UPLOAD_TTL_S + 60)

# Why a photo was rejected here; T-4.4 adds moderation's own reasons.
ABANDONED = "abandoned"
TOO_LARGE = "too_large"
UNSUPPORTED = "unsupported_format"
# A selfie uploaded and never sent to a verification, when the next one is
# asked for (T-4.5): never compared, never needed, so its file goes too. And a
# face photo no match rests on, when a new one is asked for (T-4.12).
REPLACED = "replaced"
# In a shown copy's `moderation` record: the face photo it was made from.
FROM_PHOTO_ID = "from_photo_id"

_STEP_OF = {
    PhotoKind.PUBLIC: OnboardingStep.PHOTOS,
    PhotoKind.PRIVATE: OnboardingStep.PHOTOS,
    PhotoKind.VERIFICATION: OnboardingStep.PHOTOS,
    PhotoKind.SELFIE: OnboardingStep.SELFIE,
}


def unsupported_image() -> AppError:
    """What to do, not only no (D-089)."""
    return AppError(
        "UNSUPPORTED_IMAGE",
        f"Upload a {ACCEPTED_NAMES} photo.",
        status=422,
        details={"accepted": list(ACCEPTED_TYPES)},
    )


def image_too_large() -> AppError:
    return AppError(
        "IMAGE_TOO_LARGE",
        "Photos can be up to 8 MB.",
        status=422,
        details={"max_bytes": MAX_UPLOAD_BYTES},
    )


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


async def upload_url(
    session: AsyncSession,
    user: User,
    *,
    kind: PhotoKind,
    position: int | None,
    content_type: str,
    storage: StorageProvider,
    settings: Settings,
) -> UploadUrl:
    """A place for one more photo, and the URL to upload it to."""
    # The declared type only decides what to sign; a type we'd refuse anyway
    # is refused now, with the same answer the bytes would get.
    if content_type not in ACCEPTED_TYPES:
        raise unsupported_image()
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, _STEP_OF[kind])
        _check_position(kind, position)
        live = await repository.live_photos(session, user.id, kind)
        live = await _free_abandoned(live, storage, settings)
        replaced: list[Photo] = []
        if kind is PhotoKind.SELFIE:
            live, replaced = await _replace_unsent_selfies(session, live)
        elif kind is PhotoKind.VERIFICATION:
            await _refuse_changing_the_face_photo(session, user)
            live, replaced = _replace_face_photo(live)
        _check_room(kind, position, live)
        photo_id = uuid4()
        key = raw_key(user.id, photo_id)
        repository.add(
            session,
            Photo(
                id=photo_id, user_id=user.id, kind=kind, position=position, raw_key=key
            ),
        )
    for photo in replaced:
        await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)
    signed = await storage.presign_put(
        settings.R2_BUCKET_PRIVATE,
        key,
        content_type,
        MAX_UPLOAD_BYTES,
        ttl=UPLOAD_TTL_S,
    )
    return UploadUrl(
        photo_id=photo_id, put_url=signed.url, headers=dict(signed.headers)
    )


def _check_position(kind: PhotoKind, position: int | None) -> None:
    if kind is PhotoKind.PUBLIC and position is None:
        raise invalid_field("position", "is required for a public photo: 0 to 5")
    if kind is not PhotoKind.PUBLIC and position is not None:
        raise invalid_field("position", "is only for public photos")


async def _free_abandoned(
    live: list[Photo], storage: StorageProvider, settings: Settings
) -> list[Photo]:
    """Mark rejected, as `abandoned`, every pending photo whose URL expired
    with nothing uploaded; the rest still hold their places. Asked of storage
    only for those old enough to be abandoned."""
    now = clock.now()
    holding: list[Photo] = []
    for photo in live:
        if (
            photo.status is ReviewStatus.PENDING
            and photo.created_at + ABANDONED_AFTER < now
        ):
            try:
                await storage.head(settings.R2_BUCKET_PRIVATE, photo.raw_key)
            except ObjectNotFound:
                photo.status = ReviewStatus.REJECTED
                photo.reject_reason = ABANDONED
                continue
        holding.append(photo)
    return holding


async def _replace_unsent_selfies(
    session: AsyncSession, live: list[Photo]
) -> tuple[list[Photo], list[Photo]]:
    """Mark rejected, as `replaced`, every pending selfie no verification
    holds: uploaded and never sent, so a new selfie can be. One a verification
    holds is being compared, and still holds its place. (Rejected rows are
    kept; the caller deletes their files after the commit.)"""
    waiting = [p for p in live if p.status is ReviewStatus.PENDING]
    sent = await verification_repository.selfies_submitted(
        session, [p.id for p in waiting]
    )
    replaced = [p for p in waiting if p.id not in sent]
    for photo in replaced:
        photo.status = ReviewStatus.REJECTED
        photo.reject_reason = REPLACED
    return [p for p in live if p not in replaced], replaced


async def _refuse_changing_the_face_photo(session: AsyncSession, user: User) -> None:
    """The face photo can't change once the selfie matched (the match would
    point at a photo that is gone; a change then is P-163's path), nor while a
    selfie is being compared with it (T-4.12's plan, point 4)."""
    if user.is_verified:
        raise AppError(
            "NOT_ALLOWED", "Your face photo can't change once your selfie matched."
        )
    if await verification_repository.selfie_being_compared(session, user.id):
        raise AppError(
            "NOT_ALLOWED", "Your face photo can't change while your selfie is compared."
        )


def _replace_face_photo(live: list[Photo]) -> tuple[list[Photo], list[Photo]]:
    """One live face photo per person: a new one replaces the old, pending or
    approved, as `replaced`. No match rests on it (the caller refused that), so
    nothing needs it, and the caller deletes its file after the commit."""
    for photo in live:
        photo.status = ReviewStatus.REJECTED
        photo.reject_reason = REPLACED
    return [], list(live)


def _check_room(kind: PhotoKind, position: int | None, live: list[Photo]) -> None:
    if kind is PhotoKind.PUBLIC:
        if any(photo.position == position for photo in live):
            raise AppError(
                "NOT_ALLOWED",
                "That place already has a photo. Remove it first.",
                details={"position": position},
            )
    elif kind is PhotoKind.PRIVATE:
        if len(live) >= MAX_PRIVATE:
            raise AppError(
                "NOT_ALLOWED", f"You can keep up to {MAX_PRIVATE} private photos."
            )
    elif kind is PhotoKind.SELFIE and any(
        photo.status is ReviewStatus.PENDING for photo in live
    ):
        raise AppError("NOT_ALLOWED", "Your selfie is being compared already.")
    # The face photo: `_replace_face_photo` left no live one.


async def complete(
    session: AsyncSession,
    user: User,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    queue: Queue,
    settings: Settings,
) -> PhotoOut:
    """The upload is done: check what arrived, then queue it for moderation.

    No photo moves the `photos` step on (D-392, T-4.12): `POST /me/photos/done`
    is the step's exit, with or without one. Until T-4.12 a public photo,
    pending or approved, completed it here (T-4.3).

    Saying so twice is harmless: a rejected photo stays rejected, and the
    moderation job is queued under the photo's id, so once."""
    refusal: AppError | None = None
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        photo = await repository.photo_for_update(session, user.id, photo_id)
        if photo is None:
            raise _not_found()
        if photo.status is not ReviewStatus.PENDING:
            return await _out(photo, storage, settings)
        bucket = settings.R2_BUCKET_PRIVATE
        try:
            info = await storage.head(bucket, photo.raw_key)
        except ObjectNotFound:
            raise AppError(
                "NOT_ALLOWED", "Upload the photo before saying it's done."
            ) from None
        image_type = None
        if 0 < info.size <= MAX_UPLOAD_BYTES:
            # The bytes decide (D-089). The declared type was the client's.
            image_type = sniff(
                await storage.read_prefix(bucket, photo.raw_key, SNIFF_BYTES)
            )
        if image_type is None:
            too_large = info.size > MAX_UPLOAD_BYTES
            photo.status = ReviewStatus.REJECTED
            photo.reject_reason = TOO_LARGE if too_large else UNSUPPORTED
            refusal = image_too_large() if too_large else unsupported_image()
        elif photo.kind is not PhotoKind.SELFIE:
            await queue.enqueue(
                MODERATE_PHOTO,
                job_id=f"{MODERATE_PHOTO}:{photo.id}",
                photo_id=str(photo.id),
                image_type=image_type,
            )
    if refusal is not None:
        # The row says rejected, committed; the file it never should have
        # been goes too. A delete that fails leaves it behind its row, which
        # D-078's deletion still reaches.
        await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)
        raise refusal
    return await _out(photo, storage, settings)


# --- The owner's photos (T-4.3) ---------------------------------------------------------

USER_DELETED = "user_deleted"

# The reasons an owner is told, by name (D-096): this module's, and the
# moderation reasons that say what to change (D-101). Every other reason
# reaches the owner as `other`, so a reason added later is never shown until it
# is listed here, and a possible minor (D-093) is never named to the person,
# not even in the response a browser's tools can read.
OWNER_REASONS = frozenset(
    {
        ABANDONED,
        TOO_LARGE,
        UNSUPPORTED,
        USER_DELETED,
        REPLACED,
        moderation_rules.NUDITY,
        moderation_rules.NO_FACE,
        moderation_rules.TEXT_OVERLAY,
    }
)


def owner_reason(reason: str | None) -> str | None:
    if reason is None or reason in OWNER_REASONS:
        return reason
    return moderation_rules.OTHER


async def _out(photo: Photo, storage: StorageProvider, settings: Settings) -> PhotoOut:
    """The photo for its owner, with where to view it: an approved public photo
    at the CDN; any other live one by a signed link to the private copy, 10
    minutes; a rejected one, whose file may be gone, by none."""
    url: str | None = None
    if photo.status is ReviewStatus.APPROVED and photo.public_key:
        url = public_url(settings, photo.public_key)
    elif photo.status is not ReviewStatus.REJECTED:
        url = await storage.presign_get(settings.R2_BUCKET_PRIVATE, photo.raw_key)
    return PhotoOut(
        id=photo.id,
        kind=photo.kind,
        position=photo.position,
        status=photo.status,
        reject_reason=owner_reason(photo.reject_reason),
        url=url,
        from_photo_id=made_from(photo),
    )


def made_from(photo: Photo) -> UUID | None:
    """The face photo a shown copy was made from (`show_face_photo`), else None."""
    source = (photo.moderation or {}).get(FROM_PHOTO_ID)
    return UUID(source) if photo.kind is PhotoKind.PUBLIC and source else None


async def owners_photo(
    session: AsyncSession,
    user: User,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> PhotoOut:
    """One of the user's public, private or face photos, in any status
    (D-096): how a photo that left `GET /me/photos` ended, so its slot can say
    why."""
    async with session.begin():
        photo = await repository.owners_photo(session, user.id, photo_id)
    if photo is None:
        raise _not_found()
    return await _out(photo, storage, settings)


async def owners_photos(
    session: AsyncSession, user: User, *, storage: StorageProvider, settings: Settings
) -> list[PhotoOut]:
    """Every live public, private and face photo of the user's, and nobody
    else's. Selfies are T-4.5's; rejected photos aren't live (`owners_photo`
    says how one ended, D-096)."""
    async with session.begin():
        photos = await repository.owners_view(session, user.id)
    return [await _out(photo, storage, settings) for photo in photos]


async def reorder(
    session: AsyncSession,
    user: User,
    photo_ids: list[UUID],
    *,
    storage: StorageProvider,
    settings: Settings,
) -> list[PhotoOut]:
    """Put the live public photos in this order, the first the main one: places
    0 onwards. The list must be exactly those photos, each once."""
    if len(set(photo_ids)) != len(photo_ids):
        raise invalid_field("photo_ids", "lists a photo more than once")
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, OnboardingStep.PHOTOS)
        live = await repository.live_photos(session, user.id, PhotoKind.PUBLIC)
        if {photo.id for photo in live} != set(photo_ids):
            raise invalid_field("photo_ids", "must be exactly your public photos")
        await repository.set_positions(
            session, [(photo_id, place) for place, photo_id in enumerate(photo_ids)]
        )
        photos = await repository.owners_view(session, user.id)
    return [await _out(photo, storage, settings) for photo in photos]


async def delete_photo(
    session: AsyncSession,
    user: User,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> None:
    """Remove a photo of the user's own: rejected, as `user_deleted`, so its
    place is free; its public copy, if any, removed from the public bucket.
    The private copy and the row stay (soft, as T-4.3 says). Removing it twice
    is the same as once. The last public photo may go, past the `photos` step
    too: nobody needs one (D-392, T-4.12). The face photo goes the same way,
    unless the selfie matched or is being compared; a shown copy of it is a
    public photo of its own, and stays."""
    public_key: str | None = None
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        photo = await repository.photo_for_update(session, user.id, photo_id)
        if photo is None:
            raise _not_found()
        if photo.kind is PhotoKind.SELFIE:
            raise AppError("NOT_ALLOWED", "A selfie isn't removed here.")
        if photo.status is ReviewStatus.REJECTED:
            return
        if photo.kind is PhotoKind.VERIFICATION:
            await _refuse_changing_the_face_photo(session, user)
        photo.status = ReviewStatus.REJECTED
        photo.reject_reason = USER_DELETED
        public_key = photo.public_key
    if public_key:
        await storage.delete(settings.R2_BUCKET_PUBLIC, public_key)


# --- Showing the face photo (T-4.12, D-391) -------------------------------------------

PUBLIC_PLACES = 6


async def show_face_photo(
    session: AsyncSession,
    user: User,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    queue: Queue,
    settings: Settings,
) -> PhotoOut:
    """Also show the face photo on the profile: an ordinary public photo made
    from the face photo's private copy, in the first free place, pending, and
    queued through moderation as any upload is. **Never approved at once:** a
    presigned PUT outlives `complete` by up to five minutes (P-79), so the
    face photo's private copy may not be the bytes that were scored, and a
    public copy is only ever made from scored bytes (T-4.4). So the copy goes
    the ordinary way: scored, published from what was scored, and, with a
    selfie kept, compared with it on the worker as any approved public photo
    with a face is (D-393), so the badge rests on that comparison and never
    on the verification's numbers copied over. The copy carries
    `from_photo_id`; every reader of "public photo" stays as it is; hiding it
    again is `delete_photo` on that copy. Twice is once."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, OnboardingStep.PHOTOS)
        face = await repository.photo_for_update(session, user.id, photo_id)
        if face is None or face.kind is not PhotoKind.VERIFICATION:
            raise _not_found()
        shown = await repository.shown_from(session, user.id, face.id)
        if shown is not None:
            return await _out(shown, storage, settings)
        if face.status is not ReviewStatus.APPROVED:
            raise AppError("NOT_ALLOWED", "Your face photo hasn't been approved yet.")
        taken = {
            photo.position
            for photo in await repository.live_photos(
                session, user.id, PhotoKind.PUBLIC
            )
        }
        free = next((n for n in range(PUBLIC_PLACES) if n not in taken), None)
        if free is None:
            raise AppError(
                "NOT_ALLOWED",
                "Remove a photo to make room first.",
                details={"max": PUBLIC_PLACES},
            )
        private = settings.R2_BUCKET_PRIVATE
        try:
            data = await storage.read_prefix(
                private, face.raw_key, MAX_UPLOAD_BYTES + 1
            )
        except ObjectNotFound:
            raise AppError(
                "NOT_ALLOWED", "Your face photo's file is gone. Add it again."
            ) from None
        copy_id = uuid4()
        raw = raw_key(user.id, copy_id)
        await storage.put_bytes(private, raw, data, "image/jpeg")
        copy = Photo(
            id=copy_id,
            user_id=user.id,
            kind=PhotoKind.PUBLIC,
            position=free,
            raw_key=raw,
            moderation={FROM_PHOTO_ID: str(face.id)},
        )
        repository.add(session, copy)
        await session.flush()
        await queue.enqueue(
            MODERATE_PHOTO,
            job_id=f"{MODERATE_PHOTO}:{copy.id}",
            photo_id=str(copy.id),
            image_type=sniff(data[:SNIFF_BYTES]),
        )
    return await _out(copy, storage, settings)


async def queue_match(queue: Queue, photo: Photo) -> None:
    """Compare an approved public photo with the kept selfie, for the badge
    (D-393): on the worker, one at a time, the result in the photo's record."""
    await queue.enqueue(
        MATCH_PHOTO, job_id=f"{MATCH_PHOTO}:{photo.id}", photo_id=str(photo.id)
    )


# --- Moderation (T-4.4) ----------------------------------------------------------------
#
# The worker's half of a photo: `moderate` runs as the `moderate_photo` job, which
# `complete` queues. D-092 re-encodes it, Sightengine scores it (D-094), and
# `moderation.verdict` decides. Re-running it on a decided photo changes nothing.

log = structlog.get_logger(__name__)


class TryAgain(Exception):
    """Storage or Sightengine failed for now. `moderate_photo` tries again; the
    last try logs `event` at error level and leaves the photo as it is."""

    def __init__(self, event: str, what: str) -> None:
        super().__init__(what)
        self.event = event


Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def moderate(
    sessions: Sessions,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    moderation: ModerationProvider,
    queue: Queue,
    settings: Settings,
) -> str:
    """Moderate one public, private or face photo, once: what happened, in words.

    The upload is read (at most 8 MB) and judged by its bytes again (D-089):
    its URL lasts 5 minutes, so what `complete` saw may have been replaced
    since. It is re-encoded and **written back over itself** before anything
    else, so no
    original with its location is kept, whatever happens next. Then scored, and
    the outcome recorded with the user's row locked, as every photo change is:
    - approved: a public photo's copy goes to the public bucket, from the
      bytes that were scored, never from the private copy, which a second PUT
      could have replaced since; and, if it shows a face and a selfie is kept,
      it is queued for comparison with that selfie, for the badge (D-393);
    - rejected: the re-encoded copy stays, privately, for T-9.5's review;
    - rejected as a possible minor's (D-093): a `fraud_events` signal, and the
      image and every copy deleted, each read back as gone;
    - not an image this pipeline can read, or too big: rejected `other` or
      `too_large`, its file deleted.
    """
    async with sessions() as session, session.begin():
        photo = await repository.photo_by_id(session, photo_id)
    if photo is None:
        return "no such photo: its user was refused, and it went with them"
    if photo.kind is PhotoKind.SELFIE:
        return "a selfie: T-4.5's verify_selfie checks it, not this"
    if (
        photo.status is ReviewStatus.REJECTED
        and photo.reject_reason == moderation_rules.MINOR_SUSPECTED
    ):
        # A try before this one recorded it, and its deletion didn't finish.
        await _delete_every_copy(photo, storage, settings)
        return "a possible minor's photo: every copy gone"
    if photo.status is not ReviewStatus.PENDING:
        return f"already {photo.status.value}: nothing to do"

    private = settings.R2_BUCKET_PRIVATE
    try:
        data = await storage.read_prefix(private, photo.raw_key, MAX_UPLOAD_BYTES + 1)
    except ObjectNotFound:
        log.warning("moderation.no_file", photo_id=str(photo.id))
        return "no file to moderate"
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise TryAgain("moderation.storage_failed", type(error).__name__) from None

    if len(data) > MAX_UPLOAD_BYTES:
        return await _refuse_unreadable(sessions, photo, TOO_LARGE, storage, settings)
    image_type = sniff(data[:SNIFF_BYTES])
    try:
        if image_type is None:
            raise images.UnreadableImage
        clean = images.reencode(data, image_type)
    except images.UnreadableImage:
        return await _refuse_unreadable(
            sessions, photo, moderation_rules.OTHER, storage, settings
        )
    del data
    await _stored(storage.put_bytes(private, photo.raw_key, clean.data, "image/jpeg"))

    try:
        scores = await moderation.check(clean.data)
    except ModerationFailed as failure:
        raise TryAgain("moderation.failed_photo", str(failure)) from None
    reason = moderation_rules.verdict(scores, photo.kind)

    outcome = await _record(
        sessions, photo, reason, clean, scores, storage, queue, settings
    )
    if outcome is not None:
        return outcome
    log.info(
        "moderation.decided",
        photo_id=str(photo.id),
        outcome=reason or ReviewStatus.APPROVED.value,
    )
    if reason == moderation_rules.MINOR_SUSPECTED:
        await _delete_every_copy(photo, storage, settings)
    return reason or ReviewStatus.APPROVED.value


async def _record(
    sessions: Sessions,
    photo: Photo,
    reason: moderation_rules.Reason | None,
    clean: images.Reencoded,
    scores: Scores,
    storage: StorageProvider,
    queue: Queue,
    settings: Settings,
) -> str | None:
    """Write the decision, unless the photo stopped waiting for one: None when
    written, else what stopped it."""
    async with sessions() as session, session.begin():
        try:
            user = await users_service.locked_user(session, photo.user_id)
        except LookupError:
            locked = None
        else:
            locked = await repository.photo_for_update(session, photo.user_id, photo.id)
        if locked is None:
            # Refused while this ran: the rows went, and D-078's deletion may
            # have run before the copy above was written. Don't leave it.
            await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)
            return "its user was refused while it was checked: its file removed"
        if locked.status is not ReviewStatus.PENDING:
            # Removed by its owner meanwhile (T-4.3): nothing is published.
            return f"{locked.status.value} while it was checked: left as it is"
        # A shown copy keeps which face photo it was made from (T-4.12).
        made_from = (locked.moderation or {}).get(FROM_PHOTO_ID)
        locked.moderation = {
            **({FROM_PHOTO_ID: made_from} if made_from else {}),
            **moderation_rules.summary(scores),
        }
        if reason == moderation_rules.MINOR_SUSPECTED:
            locked.status = ReviewStatus.REJECTED
            locked.reject_reason = reason
            safety_service.record_possible_minor(
                session,
                locked.user_id,
                score=max(scores.minors),
                model=MINOR_MODEL,
            )
            return None
        locked.width, locked.height = clean.width, clean.height
        if reason is not None:
            locked.status = ReviewStatus.REJECTED
            locked.reject_reason = reason
            return None
        if locked.kind is PhotoKind.PUBLIC:
            key = public_photo_key(locked.id)
            await _stored(
                storage.put_bytes(
                    settings.R2_BUCKET_PUBLIC, key, clean.data, "image/jpeg"
                )
            )
            locked.public_key = key
        locked.status = ReviewStatus.APPROVED
        if locked.kind is PhotoKind.PUBLIC and scores.minors and user.is_verified:
            await queue_match(queue, locked)
    return None


async def _refuse_unreadable(
    sessions: Sessions,
    photo: Photo,
    reason: str,
    storage: StorageProvider,
    settings: Settings,
) -> str:
    """Rejected before it was scored: nothing worth keeping, so its file goes,
    as `complete` removes a file it refuses."""
    async with sessions() as session, session.begin():
        locked = await repository.photo_for_update(session, photo.user_id, photo.id)
        if locked is None or locked.status is not ReviewStatus.PENDING:
            return "decided while it was read: left as it is"
        locked.status = ReviewStatus.REJECTED
        locked.reject_reason = reason
    await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)
    log.info("moderation.decided", photo_id=str(photo.id), outcome=reason)
    return reason


async def _delete_every_copy(
    photo: Photo, storage: StorageProvider, settings: Settings
) -> None:
    """D-093: the image and every copy of it, each read back as gone: a
    delete that answers success isn't proof the object left (D-090's rule).
    Sightengine's copy is gone by its default retention (T-4.4)."""
    copies = [
        (settings.R2_BUCKET_PRIVATE, photo.raw_key),
        (settings.R2_BUCKET_PUBLIC, public_photo_key(photo.id)),
    ]
    for bucket, key in copies:
        try:
            await storage.delete(bucket, key)
        except Exception:  # noqa: BLE001, S112 — the read-back below decides
            continue
    for bucket, key in copies:
        if not await _gone(storage, bucket, key):
            raise TryAgain(
                "moderation.minor_photo_not_deleted", "a copy is still stored"
            )


async def _gone(storage: StorageProvider, bucket: str, key: str) -> bool:
    try:
        await storage.head(bucket, key)
    except ObjectNotFound:
        return True
    except Exception:  # noqa: BLE001 — unreadable is not proof it left
        return False
    return False


async def _stored(write: Awaitable[None]) -> None:
    try:
        await write
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise TryAgain("moderation.storage_failed", type(error).__name__) from None
