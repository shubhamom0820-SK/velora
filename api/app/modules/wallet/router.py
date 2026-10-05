"""`GET /v1/wallet` and `GET /v1/wallet/ledger` (T-5.3): the owner's balance and
history, once onboarding is done.

No rate limit of their own: each reads the caller's own rows and writes
nothing, so `current_user`'s 300 a minute is the only one (02-ARCHITECTURE §12).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import onboarded_user
from app.core.pagination import PageParams, page_params
from app.modules.users.models import User
from app.modules.wallet import service
from app.modules.wallet.schemas import LedgerEntryPage, Wallet

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("")
async def wallet(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Wallet:
    return await service.balance(session, user.id)


@router.get("/ledger")
async def ledger(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
) -> LedgerEntryPage:
    return await service.ledger(session, user.id, params)
