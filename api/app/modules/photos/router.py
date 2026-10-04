"""`POST /v1/photos/upload-url` and `POST /v1/photos/{id}/complete` (T-4.2)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, current_user, user_rate_limit
from app.core.providers import Providers, get_providers
from app.core.queue import Queue, get_queue
from app.modules.photos import service
from app.modules.photos.schemas import Photo, UploadUrl, UploadUrlRequest
from app.modules.users.models import User

router = APIRouter(tags=["photos"])

# Each URL makes a row and a place held for 5 minutes: generous for anyone
# filling 6 public and 6 private places, with retries, and no more.
UPLOAD_URLS_PER_HOUR = 30


@router.post(
    "/photos/upload-url",
    dependencies=[
        Depends(
            user_rate_limit("photo_upload", limit=UPLOAD_URLS_PER_HOUR, window_s=3600)
        )
    ],
)
async def upload_url(
    body: UploadUrlRequest,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> UploadUrl:
    return await service.upload_url(
        session,
        user,
        kind=body.kind,
        position=body.position,
        content_type=body.content_type,
        storage=providers.storage,
        settings=settings,
    )


@router.post("/photos/{photo_id}/complete")
async def complete(
    photo_id: UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    queue: Annotated[Queue, Depends(get_queue)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> Photo:
    return await service.complete(
        session,
        user,
        photo_id,
        storage=providers.storage,
        queue=queue,
        settings=settings,
    )
