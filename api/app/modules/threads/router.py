"""Threads (T-7.1): open one, once onboarding is done."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import app_config_cache, app_redis, onboarded_user, user_rate_limit
from app.modules.admin.service import ConfigCache
from app.modules.threads import service
from app.modules.threads.schemas import OpenThreadRequest, Thread
from app.modules.users.models import User

router = APIRouter(tags=["threads"])

# Each open is a priced action and a lock on a pair: a double tap and then
# some, never a script working through people.
OPENS_PER_MINUTE = 20


@router.post(
    "/threads",
    dependencies=[
        Depends(user_rate_limit("threads_open", limit=OPENS_PER_MINUTE, window_s=60))
    ],
)
async def open_thread(
    body: OpenThreadRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
) -> Thread:
    return await service.open_thread(session, redis, user, body, config=config)
