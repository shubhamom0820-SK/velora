"""Gifts (T-8.9): the catalogue, sending one, and the gifts received, once
onboarding is done."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import (
    app_config_cache,
    app_settings,
    onboarded_user,
    user_rate_limit,
)
from app.core.pagination import PageParams, page_params
from app.modules.admin.service import ConfigCache
from app.modules.gifts import service
from app.modules.gifts.schemas import (
    GiftCatalogue,
    GiftCounts,
    GiftSend,
    ReceivedGiftPage,
    SendGiftRequest,
)
from app.modules.gifts.service import GiftCache
from app.modules.payments.rules import IDEMPOTENCY_KEY_PATTERN
from app.modules.users.models import User

router = APIRouter(tags=["gifts"])

# Each send is a priced action and a lock on the sender: a double tap and then
# some, never a script working through people.
SENDS_PER_MINUTE = 20


def gift_cache(request: Request) -> GiftCache:
    """This app's catalogue cache (P-47), never a process-wide one."""
    cache: GiftCache = request.app.state.gift_cache
    return cache


@router.get("/gifts")
async def list_gifts(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cache: Annotated[GiftCache, Depends(gift_cache)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
) -> GiftCatalogue:
    return await service.catalogue(session, user, cache, config=config)


@router.post(
    "/gifts/send",
    dependencies=[
        Depends(user_rate_limit("gifts_send", limit=SENDS_PER_MINUTE, window_s=60))
    ],
)
async def send_gift(
    body: SendGiftRequest,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_KEY_PATTERN)
    ],
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    config: Annotated[ConfigCache, Depends(app_config_cache)],
) -> GiftSend:
    return await service.send_gift(
        session, user, body, key=idempotency_key, config=config
    )


@router.get("/me/gifts")
async def received_gifts(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(app_settings)],
    params: Annotated[PageParams, Depends(page_params)],
) -> ReceivedGiftPage:
    return await service.received(session, user, params=params, settings=settings)


@router.get("/users/{user_id}/gifts")
async def gift_counts(
    user_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GiftCounts:
    return await service.counts(session, user, user_id)
