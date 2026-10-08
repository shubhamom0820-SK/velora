"""Messages (T-7.3, T-7.5): read a Thread's, send one, mark them read, once
onboarding is done; a voice note's file, unlocked or fetched (T-7.9)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
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
from app.core.providers import Providers, get_providers
from app.modules.admin.service import ConfigCache
from app.modules.messages import service
from app.modules.messages.schemas import (
    MediaUrl,
    Message,
    MessagePage,
    ReadRequest,
    SendMessageRequest,
    UnlockRequest,
)
from app.modules.users.models import User

router = APIRouter(tags=["messages"])

# 02-ARCHITECTURE §12: a fast typist, never a script.
SENDS_PER_MINUTE = 30
# A tap on a locked card, and its retries; never a loop.
UNLOCKS_PER_MINUTE = 30
# Each play asks for a link that lasts 10 minutes: a long scroll back, no more.
MEDIA_PER_MINUTE = 60


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
) -> MessagePage:
    return await service.list_messages(session, user, thread_id, params)


@router.post(
    "/threads/{thread_id}/messages",
    dependencies=[
        Depends(user_rate_limit("messages_send", limit=SENDS_PER_MINUTE, window_s=60))
    ],
)
async def send_message(
    thread_id: UUID,
    body: SendMessageRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> Message:
    return await service.send(
        session,
        redis,
        user,
        thread_id,
        body,
        storage=providers.storage,
        settings=settings,
        config=config,
    )


# `current_user`'s 300 a minute (02-ARCHITECTURE §12): a read that marks
# nothing tells nobody, and what one can tell is bounded by their messages.
@router.post("/threads/{thread_id}/read", status_code=204)
async def mark_read(
    thread_id: UUID,
    body: ReadRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.mark_read(session, user, thread_id, body)
    return Response(status_code=204)


@router.post(
    "/messages/{message_id}/unlock",
    dependencies=[
        Depends(
            user_rate_limit("messages_unlock", limit=UNLOCKS_PER_MINUTE, window_s=60)
        )
    ],
)
async def unlock(
    message_id: UUID,
    body: UnlockRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> MediaUrl:
    return await service.unlock(
        session,
        user,
        message_id,
        shown=body.shown_price,
        storage=providers.storage,
        settings=settings,
    )


@router.get(
    "/messages/{message_id}/media",
    dependencies=[
        Depends(user_rate_limit("messages_media", limit=MEDIA_PER_MINUTE, window_s=60))
    ],
)
async def media(
    message_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> MediaUrl:
    return await service.media(
        session, user, message_id, storage=providers.storage, settings=settings
    )
