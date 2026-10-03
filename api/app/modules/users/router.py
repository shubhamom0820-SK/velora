"""`GET /v1/me` (T-3.5): the signed-in user as the web sees them; the dob and
gender onboarding steps (T-3.6); skipping the PIN (T-3.9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import DobSet, GenderSet, Me

router = APIRouter(tags=["users"])


@router.get("/me")
async def get_me(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.me_for(session, user)


@router.post("/me/dob")
async def set_dob(
    body: DobSet,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.set_dob(session, user, body.dob)


@router.post("/me/gender")
async def set_gender(
    body: GenderSet,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.set_gender(session, user, body.gender)


@router.post("/me/pin/skip")
async def skip_pin(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.skip_pin(session, user)
