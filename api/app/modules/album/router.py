"""The private album (T-8.4): asking, her list and answer, and the album
itself, once onboarding is done."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user, user_rate_limit
from app.core.pagination import PageParams, page_params
from app.core.providers import Providers, get_providers
from app.core.queue import Queue, get_queue
from app.modules.album import service
from app.modules.album.schemas import (
    Album,
    AlbumRequest,
    AlbumRequestPage,
    CreateAlbumRequest,
    DecideAlbumRequest,
)
from app.modules.users.models import User

router = APIRouter(tags=["album"])

# A request is a priced action and a lock on the requester: a double tap and
# then some, never a script working through people.
ASKS_PER_MINUTE = 20
# Her answers and revokes: a list worked through by hand.
ANSWERS_PER_MINUTE = 60


@router.post(
    "/album-requests",
    dependencies=[
        Depends(user_rate_limit("album_ask", limit=ASKS_PER_MINUTE, window_s=60))
    ],
)
async def ask(
    body: CreateAlbumRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> AlbumRequest:
    return await service.ask(session, user, body, settings=settings)


@router.get("/album-requests/incoming")
async def incoming(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
) -> AlbumRequestPage:
    return await service.incoming(session, user, params=params, settings=settings)


@router.post(
    "/album-requests/{request_id}/decide",
    dependencies=[
        Depends(user_rate_limit("album_answer", limit=ANSWERS_PER_MINUTE, window_s=60))
    ],
)
async def decide(
    request_id: UUID,
    body: DecideAlbumRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[Queue, Depends(get_queue)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> AlbumRequest:
    return await service.decide(
        session, user, request_id, body.grant, queue=queue, settings=settings
    )


@router.post(
    "/album-requests/{request_id}/revoke",
    status_code=204,
    dependencies=[
        Depends(user_rate_limit("album_answer", limit=ANSWERS_PER_MINUTE, window_s=60))
    ],
)
async def revoke(
    request_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[Queue, Depends(get_queue)],
) -> Response:
    await service.revoke(session, user, request_id, queue=queue)
    return Response(status_code=204)


@router.get("/users/{user_id}/album")
async def album(
    user_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    queue: Annotated[Queue, Depends(get_queue)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> Album:
    return await service.album(
        session,
        user,
        user_id,
        storage=providers.storage,
        queue=queue,
        settings=settings,
    )
