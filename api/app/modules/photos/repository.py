"""SQL for photos (T-4.2). No rules here: the service decides."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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
