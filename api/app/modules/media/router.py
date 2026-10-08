"""`POST /v1/media/voice-upload-url` (T-7.9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user, user_rate_limit
from app.core.providers import Providers, get_providers
from app.modules.media import service
from app.modules.media.schemas import VoiceUpload, VoiceUploadRequest
from app.modules.users.models import User

router = APIRouter(tags=["media"])

# A URL for each recording, re-recordings and retries among them: a busy
# evening's chatting, never a loop.
VOICE_UPLOADS_PER_HOUR = 60


@router.post(
    "/media/voice-upload-url",
    dependencies=[
        Depends(
            user_rate_limit("voice_upload", limit=VOICE_UPLOADS_PER_HOUR, window_s=3600)
        )
    ],
)
async def voice_upload_url(
    body: VoiceUploadRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> VoiceUpload:
    return await service.voice_upload_url(
        session,
        user,
        body.thread_id,
        body.content_type,
        storage=providers.storage,
        settings=settings,
    )
