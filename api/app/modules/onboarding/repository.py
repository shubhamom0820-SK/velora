"""SQL for finishing onboarding (T-4.8): what the requirements read, and the
welcome grant's claim on a number (T-8.11). No rules here: the service
decides."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PhotoKind, ReviewStatus
from app.modules.onboarding.models import WelcomeGrant
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest


async def profile_of(session: AsyncSession, user_id: UUID) -> Profile:
    """The profile, read afresh: the caller has locked the user's row, which
    every onboarding write locks first, so this is what they last wrote."""
    profile: Profile | None = await session.scalar(
        select(Profile)
        .where(Profile.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise LookupError("a user without a profile: signup creates both")
    return profile


async def intent_count(session: AsyncSession, user_id: UUID) -> int:
    return await _scalar_count(
        session,
        select(func.count())
        .select_from(ProfileIntent)
        .where(ProfileIntent.user_id == user_id),
    )


async def interest_count(session: AsyncSession, user_id: UUID) -> int:
    return await _scalar_count(
        session,
        select(func.count())
        .select_from(ProfileInterest)
        .where(ProfileInterest.user_id == user_id),
    )


async def approved_public_photo_count(session: AsyncSession, user_id: UUID) -> int:
    """The user's public photos moderation approved, each with the public copy
    discovery shows."""
    return await _scalar_count(
        session,
        select(func.count())
        .select_from(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.PUBLIC,
            Photo.status == ReviewStatus.APPROVED,
            Photo.public_key.is_not(None),
        ),
    )


async def claim_welcome(session: AsyncSession, phone_hash: str, user_id: UUID) -> bool:
    """Record that this number received its welcome, for this account: True
    if it hadn't, False if it had, on this account or any before it. One
    statement, so two claims on one number can't both see it free."""
    claimed = await session.scalar(
        insert(WelcomeGrant)
        .values(phone_hash=phone_hash, user_id=user_id)
        .on_conflict_do_nothing(index_elements=[WelcomeGrant.phone_hash])
        .returning(WelcomeGrant.phone_hash)
    )
    return claimed is not None


async def _scalar_count(session: AsyncSession, query: Select[Any]) -> int:
    count: int | None = await session.scalar(query)
    return count or 0
