"""The intent catalogue and the seeking step (T-3.6); name, places, about and
username (T-3.7); the interest catalogue and the interests step (T-3.8); the
areas and the location (T-4.10)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user, user_rate_limit
from app.modules.profiles import service
from app.modules.profiles.schemas import (
    Area,
    Intent,
    Interest,
    InterestsSet,
    LocationSet,
    PositionSet,
    ProfilePatch,
    SeekingSet,
    UsernameAvailability,
    UsernameSet,
)
from app.modules.users.models import User
from app.modules.users.schemas import Me

router = APIRouter(tags=["profiles"])

# 02-ARCHITECTURE §12: checking names one keystroke at a time is fine; walking
# the list of who is on the app isn't.
USERNAME_CHECKS_PER_MINUTE = 30
# 02-ARCHITECTURE §12: onboarding's tries and a refresh each time the app opens
# fit easily. It slows someone moving themselves about to measure distances; the
# grid (D-490) is what makes their readings tell nothing finer than a cell.
LOCATION_SETS_PER_HOUR = 10


@router.get("/intents", dependencies=[Depends(current_user)])
async def list_intents(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Intent]:
    return await service.intents(session)


@router.post("/me/seeking")
async def set_seeking(
    body: SeekingSet,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.set_seeking(session, user, body.seeking, body.intent_ids)


@router.patch("/me/profile")
async def update_profile(
    body: ProfilePatch,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    changes = body.model_dump(exclude_none=True)
    return await service.update_profile(session, user, changes)


@router.get(
    "/usernames/{username}/available",
    dependencies=[
        Depends(
            user_rate_limit(
                "username_check", limit=USERNAME_CHECKS_PER_MINUTE, window_s=60
            )
        )
    ],
)
async def username_available(
    username: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UsernameAvailability:
    return await service.username_availability(session, user, username)


@router.put("/me/username")
async def set_username(
    body: UsernameSet,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.set_username(session, user, body.username)


@router.get("/interests")
async def list_interests(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Interest]:
    """Public, as 04-API marks it: a catalogue, nobody's data."""
    return await service.interests(session)


@router.put("/me/interests")
async def set_interests(
    body: InterestsSet,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.set_interests(session, user, body.interest_ids)


@router.get("/areas")
async def list_areas(
    session: Annotated[AsyncSession, Depends(get_session)],
    city: Annotated[str | None, Query(max_length=40)] = None,
) -> list[Area]:
    """Public, as 04-API marks it: reference data, nobody's. Every city's, or
    one city's, in any case; the web asks for every one, since the launch
    city lives only in the data (D-220)."""
    return await service.areas(session, city)


@router.put(
    "/me/location",
    dependencies=[
        Depends(
            user_rate_limit("location", limit=LOCATION_SETS_PER_HOUR, window_s=3600)
        )
    ],
)
async def set_location(
    body: LocationSet,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    """A shared position or a picked area (D-034, D-220). Never logged: the
    body is where the position is, and no log reads a body."""
    if isinstance(body, PositionSet):
        return await service.set_position(session, user, body.lat, body.lng)
    return await service.set_area(session, user, body.area_id)
