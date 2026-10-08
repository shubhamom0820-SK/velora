"""`GET /v1/discover` (T-6.2): the ranked feed of people nearby, once
onboarding is done.

No rate limit of its own: it reads and writes nothing of anyone's, so
`current_user`'s 300 a minute is the one (02-ARCHITECTURE §12).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user
from app.core.pagination import PageParams, page_params
from app.modules.discovery import service
from app.modules.discovery.schemas import CardPage, Feed
from app.modules.users.models import User

router = APIRouter(tags=["discovery"])

# D-041's catalogue has 10; a filter naming more than every one is no filter.
MAX_INTENT_FILTER = 10


@router.get("/discover")
async def discover(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
    feed: Feed = Feed.FORYOU,
    intent_ids: Annotated[
        list[Annotated[int, Query(ge=1, le=32767)]],
        Query(max_length=MAX_INTENT_FILTER),
    ] = [],  # noqa: B006 — FastAPI copies a query default per request
    verified: bool = False,
) -> CardPage:
    return await service.discover(
        session,
        user,
        feed=feed,
        intent_ids=intent_ids,
        verified=verified,
        params=params,
        settings=settings,
    )
