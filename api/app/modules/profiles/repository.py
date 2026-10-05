"""SQL for profiles. No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import ScalarSelect, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profiles.models import (
    Area,
    Intent,
    Interest,
    Profile,
    ProfileIntent,
    ProfileInterest,
)


async def intents(session: AsyncSession) -> list[Intent]:
    rows = await session.scalars(select(Intent).order_by(Intent.id))
    return list(rows)


async def known_intent_ids(session: AsyncSession, ids: Collection[int]) -> set[int]:
    """Which of `ids` are in the catalogue."""
    rows = await session.scalars(select(Intent.id).where(Intent.id.in_(ids)))
    return set(rows)


async def interests(session: AsyncSession) -> list[Interest]:
    rows = await session.scalars(select(Interest).order_by(Interest.id))
    return list(rows)


async def known_interest_ids(session: AsyncSession, ids: Collection[int]) -> set[int]:
    """Which of `ids` are in the catalogue."""
    rows = await session.scalars(select(Interest.id).where(Interest.id.in_(ids)))
    return set(rows)


async def replace_interests(
    session: AsyncSession, user_id: UUID, interest_ids: Collection[int]
) -> None:
    await session.execute(
        delete(ProfileInterest).where(ProfileInterest.user_id == user_id)
    )
    session.add_all(
        [ProfileInterest(user_id=user_id, interest_id=i) for i in interest_ids]
    )
    await session.flush()


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


async def username_owner(session: AsyncSession, username: str) -> UUID | None:
    """Whose profile has `username`, in any case: the column is citext."""
    owner: UUID | None = await session.scalar(
        select(Profile.user_id).where(Profile.username == username)
    )
    return owner


# --- Location (T-4.10) ------------------------------------------------------------


async def areas(session: AsyncSession, city: str | None) -> list[Area]:
    """Every area, or one city's in any case, by city then name, in any case
    whatever the database's collation."""
    query = select(Area).order_by(func.lower(Area.city), func.lower(Area.name), Area.id)
    if city is not None:
        query = query.where(func.lower(Area.city) == city.lower())
    rows = await session.scalars(query)
    return list(rows)


async def area_exists(session: AsyncSession, area_id: UUID) -> bool:
    found = await session.scalar(select(Area.id).where(Area.id == area_id))
    return found is not None


def point(lat: float, lng: float) -> Any:
    """A position as `profiles.location` stores it: a geography point, WGS 84,
    longitude first."""
    return cast(
        func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )


def centroid_of(area_id: UUID) -> ScalarSelect[Any]:
    """An area's centroid, read by the statement that stores it."""
    return select(Area.centroid).where(Area.id == area_id).scalar_subquery()


async def nearest_area_id(
    session: AsyncSession, lat: float, lng: float, within_m: float
) -> UUID | None:
    """The area whose centroid is nearest the position, if one is within
    `within_m` metres."""
    here = point(lat, lng)
    found: UUID | None = await session.scalar(
        select(Area.id)
        .where(func.ST_DWithin(Area.centroid, here, within_m))
        .order_by(func.ST_Distance(Area.centroid, here), Area.id)
        .limit(1)
    )
    return found
