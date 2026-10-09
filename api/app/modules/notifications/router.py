"""Notifications (T-9.4): push subscriptions, the settings, and the in-app list.
Each needs onboarding done, as the rest of the app does."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user, user_rate_limit
from app.core.pagination import PageParams, page_params
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    NotificationPage,
    Prefs,
    PrefsPatch,
    PushKey,
    PushSubscribed,
    PushSubscriptionIn,
    PushSubscriptionOut,
)
from app.modules.users.models import User

router = APIRouter(tags=["notifications"])

# A browser subscribes once and again only when its subscription changes; more
# than this a minute is a script, each one a row and a host we'd push to.
SUBSCRIBES_PER_MINUTE = 10
# Settings are switches a person taps; this only stops a loop.
PREF_CHANGES_PER_MINUTE = 30
READS_PER_MINUTE = 30


@router.get("/push/key")
async def push_key(
    _user: Annotated[User, Depends(onboarded_user)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> PushKey:
    return service.push_key(settings)


@router.post(
    "/push/subscriptions",
    status_code=201,
    dependencies=[
        Depends(
            user_rate_limit("push_subscribe", limit=SUBSCRIBES_PER_MINUTE, window_s=60)
        )
    ],
)
async def subscribe(
    body: PushSubscriptionIn,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PushSubscribed:
    await service.subscribe(session, user, body)
    return PushSubscribed(endpoint=body.endpoint)


@router.delete(
    "/push/subscriptions",
    status_code=204,
    dependencies=[
        Depends(
            user_rate_limit("push_subscribe", limit=SUBSCRIBES_PER_MINUTE, window_s=60)
        )
    ],
)
async def unsubscribe(
    body: PushSubscriptionOut,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.unsubscribe(session, user, body)
    return Response(status_code=204)


@router.get("/notification-prefs")
async def prefs(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Prefs:
    return await service.prefs(session, user)


@router.patch(
    "/notification-prefs",
    dependencies=[
        Depends(
            user_rate_limit(
                "notification_prefs", limit=PREF_CHANGES_PER_MINUTE, window_s=60
            )
        )
    ],
)
async def update_prefs(
    body: PrefsPatch,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Prefs:
    return await service.update_prefs(session, user, body)


@router.get("/notifications")
async def notifications(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
) -> NotificationPage:
    return await service.notifications(session, user, params)


@router.post(
    "/notifications/read",
    status_code=204,
    dependencies=[
        Depends(
            user_rate_limit("notifications_read", limit=READS_PER_MINUTE, window_s=60)
        )
    ],
)
async def mark_read(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.mark_read(session, user)
    return Response(status_code=204)
