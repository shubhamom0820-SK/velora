"""The intent catalogue and the seeking step (T-3.6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user
from app.modules.profiles import service
from app.modules.profiles.schemas import Intent, SeekingSet
from app.modules.users.models import User
from app.modules.users.schemas import Me

router = APIRouter(tags=["profiles"])


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
