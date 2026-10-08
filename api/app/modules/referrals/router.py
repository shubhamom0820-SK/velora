"""`POST /v1/referrals/apply` and `GET /v1/referrals/me` (T-8.6).

Apply is 🔐, since it is used during onboarding, and has its own limit: 10 an
hour per user, room for a few mistyped codes, while a code nobody has is a
`NOT_FOUND` that could otherwise be asked again and again to find who has one
(02-ARCHITECTURE §12). `GET /referrals/me` is ✅ and only reads, so
`current_user`'s 300 a minute is its limit.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user, onboarded_user, user_rate_limit
from app.modules.referrals import service
from app.modules.referrals.schemas import ApplyReferral, ReferralsMe
from app.modules.users.models import User

APPLIES_PER_HOUR = 10

router = APIRouter(tags=["referrals"])


@router.post(
    "/referrals/apply",
    status_code=204,
    dependencies=[
        Depends(
            user_rate_limit("referral_apply", limit=APPLIES_PER_HOUR, window_s=3600)
        )
    ],
)
async def apply_referral(
    body: ApplyReferral,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await service.apply(session, user, body.code)


@router.get("/referrals/me")
async def my_referrals(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReferralsMe:
    return await service.me(session, user)
