"""The intent catalogue and the seeking step (T-3.6); name, places, about and
username (T-3.7); the interest catalogue and the interests step (T-3.8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user, user_rate_limit
from app.modules.profiles import service
from app.modules.profiles.schemas import (
    Intent,
    Interest,
    InterestsSet,
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
