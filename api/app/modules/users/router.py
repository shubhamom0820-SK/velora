"""`GET /v1/me` (T-3.5): the signed-in user as the web sees them."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import Me

router = APIRouter(tags=["users"])


@router.get("/me")
async def get_me(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Me:
    return await service.me_for(session, user)
