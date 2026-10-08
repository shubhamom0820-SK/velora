"""`GET /v1/likes`, `GET /v1/likes/count` and `POST /v1/likes/{handle}/reveal`
(T-6.7, D-542), once onboarding is done.

No rate limit of their own: `current_user`'s 300 a minute (02-ARCHITECTURE
§12). A reveal is paid, and paid once per pair, so repeating it costs nothing
and finds nothing new.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user
from app.core.pagination import PageParams, page_params
from app.core.queue import Queue, get_queue
from app.modules.discovery.schemas import PublicProfile
from app.modules.likes import service
from app.modules.likes.schemas import LikeCardPage, LikesCount, RevealRequest
from app.modules.users.models import User

router = APIRouter(tags=["likes"])


@router.get("/likes")
async def likes(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
    queue: Annotated[Queue, Depends(get_queue)],
) -> LikeCardPage:
    return await service.likes(
        session, user, params=params, settings=settings, queue=queue
    )


@router.get("/likes/count")
async def likes_count(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> LikesCount:
    return await service.count(session, user, settings=settings)


@router.post("/likes/{handle}/reveal")
async def reveal(
    handle: str,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    body: RevealRequest | None = None,
) -> PublicProfile:
    body = body or RevealRequest()
    return await service.reveal(
        session, user, handle, shown_price=body.shown_price, settings=settings
    )
