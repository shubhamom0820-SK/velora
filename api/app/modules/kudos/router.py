"""Kudos (T-8.5): give one, and see your own, once onboarding is done."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import app_config_cache, onboarded_user, user_rate_limit
from app.modules.admin.service import ConfigCache
from app.modules.kudos import service
from app.modules.kudos.schemas import GiveKudosRequest, Kudos, KudosGiven
from app.modules.users.models import User

router = APIRouter(tags=["kudos"])

# 02-ARCHITECTURE §12: one per person ever, so a person giving them never
# needs more; a script trying ids does.
GIVES_PER_MINUTE = 10


@router.post(
    "/kudos",
    status_code=201,
    dependencies=[
        Depends(user_rate_limit("kudos_give", limit=GIVES_PER_MINUTE, window_s=60))
    ],
)
async def give_kudos(
    body: GiveKudosRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
) -> KudosGiven:
    return await service.give(session, user, body, config=config)


@router.get("/me/kudos")
async def my_kudos(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Kudos]:
    return await service.mine(session, user)
