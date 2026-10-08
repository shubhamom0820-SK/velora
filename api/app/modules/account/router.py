"""Settings and data rights (T-9.6): the privacy switches, pausing, exporting
one's own data and deleting the account. Each needs onboarding done (04-API)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user, user_rate_limit
from app.core.providers import Providers, get_providers
from app.core.queue import Queue, get_queue
from app.modules.account import service
from app.modules.account.schemas import DataExport, DeletionScheduled, SettingsPatch
from app.modules.users.models import User
from app.modules.users.schemas import Me

router = APIRouter(tags=["account"])

# Asking again returns the export being made, so this only stops a loop: a
# stuck one is retried after an hour, a ready one lasts a day (D-502).
EXPORTS_PER_DAY = 5


@router.patch("/me/settings")
async def update_settings(
    body: SettingsPatch,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.update_settings(session, user, body)


@router.post("/me/pause", status_code=204)
async def pause(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.pause(session, user)
    return Response(status_code=204)


@router.delete("/me/pause", status_code=204)
async def resume(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.resume(session, user)
    return Response(status_code=204)


@router.post(
    "/me/export",
    status_code=202,
    dependencies=[
        Depends(user_rate_limit("export", limit=EXPORTS_PER_DAY, window_s=86_400))
    ],
)
async def request_export(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    queue: Annotated[Queue, Depends(get_queue)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> DataExport:
    return await service.request_export(
        session, user, queue=queue, storage=providers.storage, settings=settings
    )


@router.get("/me/export")
async def latest_export(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> DataExport:
    return await service.latest_export(
        session, user, storage=providers.storage, settings=settings
    )


@router.delete("/me", status_code=202)
async def delete_account(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeletionScheduled:
    return await service.delete_account(session, user)
