"""`GET /v1/prices` (T-5.2): public, with no rate limit of its own.

It reads one small table and writes nothing, as `/readyz` does with no limit;
a per-IP limit on a public read would mostly catch men behind one carrier's
shared address. Flooding is the edge's to stop (02-ARCHITECTURE §12).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.pricing import service
from app.modules.pricing.schemas import Prices

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("")
async def list_prices(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Prices:
    return Prices(await service.active_prices(session))
