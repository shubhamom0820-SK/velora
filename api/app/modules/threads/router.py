"""Threads (T-7.1, T-7.2, T-7.8): open one, list them, read one, clear one from
your own chats, once onboarding is done."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import (
    app_config_cache,
    app_redis,
    app_settings,
    onboarded_user,
    user_rate_limit,
)
from app.core.pagination import PageParams, page_params
from app.modules.admin.service import ConfigCache
from app.modules.threads import service
from app.modules.threads.schemas import (
    Q_MAX,
    Cleared,
    ClearThreadsRequest,
    OpenThreadRequest,
    Thread,
    ThreadRowPage,
)
from app.modules.users.models import User

router = APIRouter(tags=["threads"])

# Each open is a priced action and a lock on a pair: a double tap and then
# some, never a script working through people.
OPENS_PER_MINUTE = 20

# Clearing, its bulk form and its undo share one bucket: a busy thumb in select
# mode and its undo toasts, never a script.
CLEARS_PER_MINUTE = 60
clear_rate_limit = Depends(
    user_rate_limit("threads_clear", limit=CLEARS_PER_MINUTE, window_s=60)
)


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


@router.get("/threads")
async def list_threads(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
    tier: service.Tier = "threads",
    filter_: Annotated[service.Filter, Query(alias="filter")] = "all",
    q: Annotated[str | None, Query(min_length=1, max_length=Q_MAX)] = None,
) -> ThreadRowPage:
    return await service.list_threads(
        session,
        user,
        tier=tier,
        filter_=filter_,
        q=q,
        params=params,
        settings=settings,
    )


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Thread:
    return await service.get_thread(session, user, thread_id)


@router.post("/threads/clear", dependencies=[clear_rate_limit])
async def clear_threads(
    body: ClearThreadsRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Cleared:
    return await service.clear_many(session, user, body)


@router.post(
    "/threads/{thread_id}/clear", status_code=204, dependencies=[clear_rate_limit]
)
async def clear_thread(
    thread_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.clear(session, user, thread_id)
    return Response(status_code=204)


@router.delete(
    "/threads/{thread_id}/clear", status_code=204, dependencies=[clear_rate_limit]
)
async def restore_thread(
    thread_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.restore(session, user, thread_id)
    return Response(status_code=204)
