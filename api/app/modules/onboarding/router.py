"""Finishing onboarding (T-4.8): `selfie` to `done`, or why not yet; and the
`photos` step's exit (T-4.12), `POST /v1/me/photos/done`, beside
`/me/photos/order`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user
from app.modules.onboarding import service
from app.modules.users.models import User
from app.modules.users.schemas import Me

router = APIRouter(tags=["onboarding"])


# No rate limit, like every other onboarding step: a few reads and one row,
# and nothing sent anywhere.
@router.post("/me/photos/done")
async def leave_photos(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.leave_photos(session, user)


@router.post("/me/onboarding/complete")
async def complete_onboarding(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.complete(session, user)
