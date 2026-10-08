"""`GET /v1/discover` (T-6.2): the ranked feed of people nearby;
`GET /v1/users/{id}` (T-6.3) and `GET /v1/users/by-username/{u}` (T-6.6), one
person's public profile; and `GET /v1/search` (T-6.6); once onboarding is done.

No rate limit of their own but search's: `current_user`'s 300 a minute
(02-ARCHITECTURE §12). A profile is found by its id, a UUID nobody can walk,
or by its username, which is the link people share (D-001). Search walks
usernames by their start, so it has its own limit.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import (
    app_config_cache,
    app_redis,
    app_settings,
    onboarded_user,
    rate_limit,
    user_rate_limit,
)
from app.core.pagination import PageParams, page_params
from app.modules.admin.service import ConfigCache
from app.modules.discovery import rules, service
from app.modules.discovery.schemas import (
    CardPage,
    Feed,
    PublicProfile,
    SearchResultPage,
    SharedProfile,
)
from app.modules.users.models import User

router = APIRouter(tags=["discovery"])

# D-041's catalogue has 10; a filter naming more than every one is no filter.
MAX_INTENT_FILTER = 10
# Search walks usernames by their start (D-540): a person typing, never a script.
SEARCHES_PER_MINUTE = 60
# `/@username` for anyone, signed in or not (D-544): a page someone shares, read
# a few times; a script walking usernames is held to this, per address.
SHARED_PER_MINUTE = 60


@router.get("/discover")
async def discover(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(app_redis)],
    settings: Annotated[Settings, Depends(app_settings)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
    params: Annotated[PageParams, Depends(page_params)],
    feed: Feed = Feed.FORYOU,
    intent_ids: Annotated[
        list[Annotated[int, Query(ge=1, le=32767)]],
        Query(max_length=MAX_INTENT_FILTER),
    ] = [],  # noqa: B006 — FastAPI copies a query default per request
    verified: bool = False,
    online: bool = False,
) -> CardPage:
    return await service.discover(
        session,
        redis,
        user,
        feed=feed,
        intent_ids=intent_ids,
        verified=verified,
        online=online,
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


@router.get("/users/by-username/{username}")
async def profile_by_username(
    username: str,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> PublicProfile:
    return await service.profile_by_username(session, user, username, settings=settings)


@router.get(
    "/search",
    dependencies=[
        Depends(user_rate_limit("search", limit=SEARCHES_PER_MINUTE, window_s=60))
    ],
)
async def search(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str, Query(min_length=1, max_length=rules.SEARCH_MAX)],
) -> SearchResultPage:
    return await service.search(
        session, user, q, params=params, settings=settings, config=config
    )


@router.get(
    "/public-profiles/{username}",
    dependencies=[
        Depends(rate_limit("public_profiles", limit=SHARED_PER_MINUTE, window_s=60))
    ],
)
async def shared_profile(
    username: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> SharedProfile:
    """Public: the `/@username` page asks it as its visitor, signed in or not."""
    return await service.shared_profile(session, username, settings=settings)
