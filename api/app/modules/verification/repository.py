"""SQL for verifications (T-4.5). No rules here: the service decides."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, PhotoKind, ReviewStatus
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification.models import Verification


def add(session: AsyncSession, verification: Verification) -> None:
    session.add(verification)


async def latest(session: AsyncSession, user_id: UUID) -> Verification | None:
    """The user's newest verification."""
    verification: Verification | None = await session.scalar(
        select(Verification)
        .where(Verification.user_id == user_id)
        .order_by(Verification.created_at.desc(), Verification.id)
        .limit(1)
    )
    return verification


async def pending(session: AsyncSession, user_id: UUID) -> list[Verification]:
    """The user's verifications not yet decided, oldest first."""
    rows = await session.scalars(
        select(Verification)
        .where(
            Verification.user_id == user_id,
            Verification.status == ReviewStatus.PENDING,
        )
        .order_by(Verification.created_at)
    )
    return list(rows)


async def for_update(
    session: AsyncSession, user_id: UUID, verification_id: UUID
) -> Verification | None:
    """The user's own verification, locked; None if there's none or it's
    someone else's: one answer for both, so ids can't be probed."""
    verification: Verification | None = await session.scalar(
        select(Verification)
        .where(Verification.id == verification_id, Verification.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return verification


async def by_id(session: AsyncSession, verification_id: UUID) -> Verification | None:
    """Any verification, unlocked: the worker's first look."""
    verification: Verification | None = await session.get(
        Verification, verification_id, populate_existing=True
    )
    return verification


async def submitted_since(
    session: AsyncSession, user_id: UUID, since: datetime
) -> list[datetime]:
    """When each of the user's verifications started since `since`, among
    those a selfie was submitted to: the attempts that count."""
    rows = await session.scalars(
        select(Verification.created_at)
        .where(
            Verification.user_id == user_id,
            Verification.selfie_photo_id.is_not(None),
            Verification.created_at > since,
        )
        .order_by(Verification.created_at)
    )
    return list(rows)


async def selfies_submitted(
    session: AsyncSession, photo_ids: Sequence[UUID]
) -> set[UUID]:
    """Which of these selfies a verification already holds."""
    if not photo_ids:
        return set()
    rows = await session.scalars(
        select(Verification.selfie_photo_id).where(
            Verification.selfie_photo_id.in_(photo_ids)
        )
    )
    return {photo_id for photo_id in rows if photo_id is not None}


async def approved_public_photos(session: AsyncSession, user_id: UUID) -> list[Photo]:
    """The photos a selfie is compared with: the user's approved public ones,
    by place."""
    rows = await session.scalars(
        select(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.PUBLIC,
            Photo.status == ReviewStatus.APPROVED,
            Photo.public_key.is_not(None),
        )
        .order_by(Photo.position, Photo.created_at)
    )
    return list(rows)


async def public_photos_waiting(session: AsyncSession, user_id: UUID) -> int:
    """How many of the user's public photos moderation hasn't decided yet."""
    count: int = (
        await session.scalar(
            select(func.count())
            .select_from(Photo)
            .where(
                Photo.user_id == user_id,
                Photo.kind == PhotoKind.PUBLIC,
                Photo.status == ReviewStatus.PENDING,
            )
        )
        or 0
    )
    return count


async def decided_since(
    session: AsyncSession, since: datetime
) -> list[tuple[Verification, Photo, Gender | None]]:
    """Every verification decided since `since`, newest first, each with its
    selfie and whose it is: what the founder's review reads (D-264)."""
    rows = await session.execute(
        select(Verification, Photo, User.gender)
        .join(Photo, Photo.id == Verification.selfie_photo_id)
        .join(User, User.id == Verification.user_id)
        .where(
            Verification.status != ReviewStatus.PENDING,
            Verification.updated_at > since,
        )
        .order_by(Verification.updated_at.desc(), Verification.id)
    )
    return [(v, photo, gender) for v, photo, gender in rows.tuples()]


async def photos_by_id(session: AsyncSession, photo_ids: Sequence[UUID]) -> list[Photo]:
    if not photo_ids:
        return []
    return list(await session.scalars(select(Photo).where(Photo.id.in_(photo_ids))))


async def selfie_of(session: AsyncSession, verification_id: UUID) -> Photo | None:
    """A verification's selfie, locked: the review writes its verdict there."""
    photo: Photo | None = await session.scalar(
        select(Photo)
        .join(Verification, Verification.selfie_photo_id == Photo.id)
        .where(Verification.id == verification_id)
        .with_for_update(of=Photo)
    )
    return photo
