"""`/v1/admin/*` (04-API.md). T-9.5 builds the panel's routes; T-8.1 the first,
`GET /admin/turnover`.

Admin only, never a moderator: it is the company's revenue (D-483). Every call
writes `audit_log` (02-ARCHITECTURE §12).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_role
from app.core.enums import Role
from app.modules.payments import service as payments_service
from app.modules.payments.schemas import Turnover
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/turnover")
async def turnover(
    admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    year: Annotated[
        int | None,
        Query(
            ge=2026,
            le=2100,
            description="The financial year's first year: 2026 is 2026-27. This one if absent.",
        ),
    ] = None,
) -> Turnover:
    return await payments_service.turnover_for_admin(session, admin.id, year)
