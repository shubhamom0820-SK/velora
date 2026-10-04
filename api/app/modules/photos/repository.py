"""SQL for photos (T-4.2). No rules here: the service decides."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PhotoKind, ReviewStatus
from app.modules.photos.models import Photo


async def live_photos(
    session: AsyncSession, user_id: UUID, kind: PhotoKind
) -> list[Photo]:
    """The user's photos of `kind` that hold a place: every one not rejected."""
    rows = await session.scalars(
        select(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind == kind,
            Photo.status != ReviewStatus.REJECTED,
        )
        .order_by(Photo.created_at)
    )
    return list(rows)


def add(session: AsyncSession, photo: Photo) -> None:
    session.add(photo)


async def photo_by_id(session: AsyncSession, photo_id: UUID) -> Photo | None:
    """Any photo, unlocked: the worker's first look (T-4.4)."""
    photo: Photo | None = await session.get(Photo, photo_id)
    return photo


async def photo_for_update(
    session: AsyncSession, user_id: UUID, photo_id: UUID
) -> Photo | None:
    """The user's own photo, locked; None if there's none, or it's someone
    else's: the same answer for both, so ids can't be probed."""
    photo: Photo | None = await session.scalar(
        select(Photo)
        .where(Photo.id == photo_id, Photo.user_id == user_id)
        .with_for_update()
    )
    return photo


async def owners_photo(
    session: AsyncSession, user_id: UUID, photo_id: UUID
) -> Photo | None:
    """One public or private photo of the user's, in any status; None if
    there's none, it's someone else's, or it's a selfie: the same answer for
    each, so ids can't be probed."""
    photo: Photo | None = await session.scalar(
        select(Photo).where(
            Photo.id == photo_id,
            Photo.user_id == user_id,
            Photo.kind.in_((PhotoKind.PUBLIC, PhotoKind.PRIVATE)),
        )
    )
    return photo


async def owners_view(session: AsyncSession, user_id: UUID) -> list[Photo]:
    """The user's live public and private photos, public first by place, then
    private oldest first. Selfies are T-4.5's, never listed here."""
    rows = await session.scalars(
        select(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind.in_((PhotoKind.PUBLIC, PhotoKind.PRIVATE)),
            Photo.status != ReviewStatus.REJECTED,
        )
        .order_by(Photo.kind, Photo.position, Photo.created_at)
        # Read fresh: after `set_positions`, the session still holds these
        # photos with their old places.
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def set_positions(
    session: AsyncSession, positions: list[tuple[UUID, int]]
) -> None:
    """Move public photos to new places, in the caller's transaction.

    The one-photo-per-place index (public, not rejected) is checked row by
    row, so two photos swapping places would collide with each other halfway
    through. So the photos step out of the index first, by being marked
    rejected for the length of this transaction, move, and step back in with
    their own statuses. No other transaction ever sees the middle."""
    ids = [photo_id for photo_id, _ in positions]
    rows = await session.execute(
        select(Photo.id, Photo.status).where(Photo.id.in_(ids))
    )
    statuses = {photo_id: status for photo_id, status in rows.tuples()}
    await session.execute(
        update(Photo)
        .where(Photo.id.in_(ids))
        .values(status=ReviewStatus.REJECTED)
        .execution_options(synchronize_session=False)
    )
    for photo_id, position in positions:
        await session.execute(
            update(Photo)
            .where(Photo.id == photo_id)
            .values(position=position, status=statuses[photo_id])
            .execution_options(synchronize_session=False)
        )
