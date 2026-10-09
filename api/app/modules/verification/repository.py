"""SQL for verifications (T-4.5). No rules here: the service decides."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, select
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


async def selfie_being_compared(session: AsyncSession, user_id: UUID) -> bool:
    """Whether a verification of the user's holds a selfie and isn't decided:
    the worker may be comparing it with the face photo right now."""
    found = await session.scalar(
        select(Verification.id)
        .where(
            Verification.user_id == user_id,
            Verification.status == ReviewStatus.PENDING,
            Verification.selfie_photo_id.is_not(None),
        )
        .limit(1)
    )
    return found is not None


async def face_photo(session: AsyncSession, user_id: UUID) -> Photo | None:
    """The photo a selfie is compared with (D-391): the user's approved face
    photo. One live per person (`photos.service`), so at most one."""
    photo: Photo | None = await session.scalar(
        select(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.VERIFICATION,
            Photo.status == ReviewStatus.APPROVED,
        )
        .order_by(Photo.created_at.desc())
        .limit(1)
    )
    return photo


async def face_photo_waiting(session: AsyncSession, user_id: UUID) -> bool:
    """Whether the user's face photo is still being moderated."""
    found = await session.scalar(
        select(Photo.id)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.VERIFICATION,
            Photo.status == ReviewStatus.PENDING,
        )
        .limit(1)
    )
    return found is not None


async def shown_photos_with_a_face(session: AsyncSession, user_id: UUID) -> list[Photo]:
    """The public photos the badge may rest on (D-393): the user's approved
    ones whose moderation record found a real face, by place."""
    rows = await session.scalars(
        select(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.PUBLIC,
            Photo.status == ReviewStatus.APPROVED,
            Photo.public_key.is_not(None),
            Photo.moderation["faces"].as_integer() >= 1,
        )
        .order_by(Photo.position, Photo.created_at)
    )
    return list(rows)


async def kept_selfie(
    session: AsyncSession, user_id: UUID
) -> tuple[Verification, Photo] | None:
    """The user's approved verification and its selfie (the kept one, D-393),
    or None: nothing to compare a shown photo with."""
    row = (
        await session.execute(
            select(Verification, Photo)
            .join(Photo, Photo.id == Verification.selfie_photo_id)
            .where(
                Verification.user_id == user_id,
                Verification.status == ReviewStatus.APPROVED,
            )
            .order_by(Verification.updated_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    verification, selfie = row.tuple()
    return verification, selfie


def badge_of(user_id: Any, is_verified: Any) -> ColumnElement[bool]:
    """The badge for the user whose id and `is_verified` are these columns of
    the caller's query: `is_verified` (the selfie matched the face photo,
    D-393) and **the main photo's** face matched that selfie (D-910). The main
    photo is the card's: the approved public photo at the lowest place
    (`discovery.repository.main_photo_key`, P-75), so a new main photo, or a
    reorder that puts another first, carries no badge until it is compared and
    matches; a match elsewhere on the profile never lends it one. Never
    `is_verified` alone. One rule for `shows_badge` and discovery's `Card` and
    filter (T-6.2)."""
    main_matched = (
        select(Photo.moderation["selfie_match"]["matched"].as_boolean())
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.PUBLIC,
            Photo.status == ReviewStatus.APPROVED,
            Photo.public_key.is_not(None),
        )
        .order_by(Photo.position, Photo.id)
        .limit(1)
        .scalar_subquery()
    )
    return and_(is_verified.is_(True), main_matched.is_(True))


async def shows_badge(session: AsyncSession, user_id: UUID) -> bool:
    """The badge for one user, by `badge_of` (D-393, D-910)."""
    found = await session.scalar(
        select(User.id).where(User.id == user_id, badge_of(User.id, User.is_verified))
    )
    return found is not None


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
