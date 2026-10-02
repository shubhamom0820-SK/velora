"""`POST /v1/waitlist` (T-2.3): public, and rate-limited per client IP."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import rate_limit
from app.modules.waitlist import service
from app.modules.waitlist.schemas import WaitlistJoin, WaitlistJoined

# 02-ARCHITECTURE.md §12: 5 a minute per IP, invalid tries included.
WAITLIST_LIMIT = 5
WAITLIST_WINDOW_S = 60

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post(
    "",
    status_code=201,
    dependencies=[
        Depends(
            rate_limit("waitlist", limit=WAITLIST_LIMIT, window_s=WAITLIST_WINDOW_S)
        )
    ],
)
async def join_waitlist(
    body: WaitlistJoin, session: Annotated[AsyncSession, Depends(get_session)]
) -> WaitlistJoined:
    await service.join(session, email=body.email, city=body.city)
    return WaitlistJoined()
