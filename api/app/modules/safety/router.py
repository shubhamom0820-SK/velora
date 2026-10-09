"""Reports and blocks (T-9.1), once onboarding is done (04-API.md)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user, user_rate_limit
from app.core.pagination import PageParams, page_params
from app.core.queue import Queue, get_queue
from app.modules.safety import service
from app.modules.safety.schemas import (
    BlockedUser,
    BlockedUserPage,
    BlockRequest,
    FiledReportPage,
    FileReportRequest,
    ReportFiled,
)
from app.modules.users.models import User

router = APIRouter(tags=["safety"])

# 02-ARCHITECTURE §12: ten reports a day per user. More than that from one
# person is noise in moderation's queue, never more safety.
REPORTS_PER_DAY = 10
# Blocks and unblocks together: a person tidying their list never needs more;
# each one writes a row that is kept (D-860), so churn is bounded.
BLOCKS_PER_MINUTE = 60

_blocks_limit = user_rate_limit("blocks", limit=BLOCKS_PER_MINUTE, window_s=60)


@router.post(
    "/reports",
    status_code=201,
    dependencies=[
        Depends(user_rate_limit("reports", limit=REPORTS_PER_DAY, window_s=86_400))
    ],
)
async def file_report(
    body: FileReportRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[Queue, Depends(get_queue)],
) -> ReportFiled:
    return await service.report(session, user, body, queue=queue)


@router.get("/reports")
async def list_filed_reports(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
) -> FiledReportPage:
    return await service.filed_reports(session, user, params=params, settings=settings)


@router.post("/blocks", status_code=201, dependencies=[Depends(_blocks_limit)])
async def block(
    body: BlockRequest,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[Queue, Depends(get_queue)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> BlockedUser:
    return await service.block(
        session, user, body.user_id, queue=queue, settings=settings
    )


@router.delete(
    "/blocks/{user_id}", status_code=204, dependencies=[Depends(_blocks_limit)]
)
async def unblock(
    user_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.unblock(session, user, user_id)
    return Response(status_code=204)


@router.get("/blocks")
async def list_blocks(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
) -> BlockedUserPage:
    return await service.blocks(session, user, params=params, settings=settings)
