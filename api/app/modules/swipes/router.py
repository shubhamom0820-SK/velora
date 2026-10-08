"""`POST /v1/swipes` (T-6.4): swipe, match, once onboarding is done."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import app_config_cache, app_redis, onboarded_user, user_rate_limit
from app.modules.admin.service import ConfigCache
from app.modules.swipes import service
from app.modules.swipes.schemas import SwipeRequest, SwipeResult
from app.modules.users.models import User

router = APIRouter(tags=["swipes"])

# 02-ARCHITECTURE §12: a fast thumb, never a script; men's daily cap is
# separate and counted by the service.
SWIPES_PER_MINUTE = 120


@router.post(
    "/swipes",
    dependencies=[
        Depends(user_rate_limit("swipes", limit=SWIPES_PER_MINUTE, window_s=60))
    ],
)
async def swipe(
    body: SwipeRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
) -> SwipeResult:
    return await service.swipe(
        session, redis, user, body.target_id, body.dir, config=config
    )
