"""`GET /v1/discover` (T-6.2): the ranked feed of people nearby; and
`GET /v1/users/{id}` (T-6.3), one person's public profile; once onboarding is
done.

No rate limit of their own: `current_user`'s 300 a minute (02-ARCHITECTURE
§12). A profile is found by its id, a UUID nobody can walk.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_config_cache, app_settings, onboarded_user
from app.core.pagination import PageParams, page_params
from app.modules.admin.service import ConfigCache
from app.modules.discovery import service
from app.modules.discovery.schemas import CardPage, Feed, PublicProfile
from app.modules.users.models import User

router = APIRouter(tags=["discovery"])

# D-041's catalogue has 10; a filter naming more than every one is no filter.
MAX_INTENT_FILTER = 10


@router.get("/discover")
async def discover(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
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
        config=config,
    )


@router.get("/users/{user_id}")
async def public_profile(
    user_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> PublicProfile:
    return await service.public_profile(session, user, user_id, settings=settings)
