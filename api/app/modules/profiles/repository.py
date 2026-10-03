"""SQL for profiles. No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profiles.models import Intent, Profile, ProfileIntent


async def intents(session: AsyncSession) -> list[Intent]:
    rows = await session.scalars(select(Intent).order_by(Intent.id))
    return list(rows)


async def known_intent_ids(session: AsyncSession, ids: Collection[int]) -> set[int]:
    """Which of `ids` are in the catalogue."""
    rows = await session.scalars(select(Intent.id).where(Intent.id.in_(ids)))
    return set(rows)


async def profile_of(session: AsyncSession, user_id: UUID) -> Profile:
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise LookupError("a user without a profile: signup creates both")
    return profile


async def replace_intents(
    session: AsyncSession, user_id: UUID, intent_ids: Collection[int]
) -> None:
    await session.execute(delete(ProfileIntent).where(ProfileIntent.user_id == user_id))
    session.add_all(
        [
            ProfileIntent(user_id=user_id, intent_id=intent_id)
            for intent_id in intent_ids
        ]
    )
    await session.flush()
