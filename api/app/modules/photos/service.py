"""Uploading a photo (T-4.2): a presigned PUT, then `complete`.

The browser uploads straight to the private bucket (D-027); the server never
handles the bytes on the way in. `complete` then checks what arrived: that it
exists, its size, and what it is by its first bytes, never by the type the
browser declared (D-089). An accepted public or private photo is queued for
moderation (T-4.4); a selfie waits for T-4.5's submit.

Public and private photos are D-068's `photos` step, the selfie its `selfie`
step: each works at its step or after, never before.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.errors import AppError, invalid_field
from app.core.images import ACCEPTED_NAMES, ACCEPTED_TYPES, SNIFF_BYTES, sniff
from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.queue import MODERATE_PHOTO, Queue
from app.core.storage_keys import raw_key
from app.modules.photos import repository
from app.modules.photos.models import Photo
from app.modules.photos.schemas import Photo as PhotoOut
from app.modules.photos.schemas import UploadUrl
from app.modules.users import service as users_service
from app.modules.users.models import User

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

_STEP_OF = {
    PhotoKind.PUBLIC: OnboardingStep.PHOTOS,
    PhotoKind.PRIVATE: OnboardingStep.PHOTOS,
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
        _check_room(kind, position, live)
        photo_id = uuid4()
        key = raw_key(user.id, photo_id)
        repository.add(
            session,
            Photo(
                id=photo_id, user_id=user.id, kind=kind, position=position, raw_key=key
            ),
        )
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
    elif any(photo.status is ReviewStatus.PENDING for photo in live):
        raise AppError("NOT_ALLOWED", "Your selfie is already waiting to be checked.")


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

    Saying so twice is harmless: a rejected photo stays rejected, and the
    moderation job is queued under the photo's id, so once."""
    refusal: AppError | None = None
    async with session.begin():
        photo = await repository.photo_for_update(session, user.id, photo_id)
        if photo is None:
            raise _not_found()
        if photo.status is not ReviewStatus.PENDING:
            return PhotoOut.model_validate(photo)
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
        out = PhotoOut.model_validate(photo)
    if refusal is not None:
        # The row says rejected, committed; the file it never should have
        # been goes too. A delete that fails leaves it behind its row, which
        # D-078's deletion still reaches.
        await storage.delete(settings.R2_BUCKET_PRIVATE, photo.raw_key)
        raise refusal
    return out
