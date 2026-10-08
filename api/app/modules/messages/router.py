"""Messages (T-7.3, T-7.5): read a Thread's, send one, mark them read, once
onboarding is done."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import app_config_cache, app_redis, onboarded_user, user_rate_limit
from app.core.pagination import PageParams, page_params
from app.modules.admin.service import ConfigCache
from app.modules.messages import service
from app.modules.messages.schemas import (
    Message,
    MessagePage,
    ReadRequest,
    SendMessageRequest,
)
from app.modules.users.models import User

router = APIRouter(tags=["messages"])

# 02-ARCHITECTURE §12: a fast typist, never a script.
SENDS_PER_MINUTE = 30


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
) -> Message:
    return await service.send(session, redis, user, thread_id, body, config=config)


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
