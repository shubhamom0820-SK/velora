"""`POST /v1/verification/start`, `POST /v1/verification/{id}/submit` and
`GET /v1/verification/latest` (T-4.5)."""

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
from app.modules.users.models import User
from app.modules.verification import service
from app.modules.verification.schemas import SubmitSelfie, Verification

router = APIRouter(tags=["verification"])

# Each is a tap on the selfie screen. The day's five selfies are the real
# limit (rules.ATTEMPTS); these only stop a loop.
STARTS_PER_HOUR = 20
SUBMITS_PER_HOUR = 20


@router.post(
    "/verification/start",
    dependencies=[
        Depends(
            user_rate_limit("verification_start", limit=STARTS_PER_HOUR, window_s=3600)
        )
    ],
)
async def start(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Verification:
    return await service.start(session, user)


@router.post(
    "/verification/{verification_id}/submit",
    dependencies=[
        Depends(
            user_rate_limit(
                "verification_submit", limit=SUBMITS_PER_HOUR, window_s=3600
            )
        )
    ],
)
async def submit(
    verification_id: UUID,
    body: SubmitSelfie,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    queue: Annotated[Queue, Depends(get_queue)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> Verification:
    return await service.submit(
        session,
        user,
        verification_id,
        body.photo_id,
        storage=providers.storage,
        queue=queue,
        settings=settings,
    )


@router.get("/verification/latest")
async def latest(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Verification:
    return await service.latest(session, user)
