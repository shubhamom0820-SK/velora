"""`/v1/admin/*` (04-API.md). T-9.5 builds the panel's routes; T-8.1 the first,
`GET /admin/turnover`; T-8.3 the claims, `GET /admin/refund-requests` and
`POST /admin/refund-requests/{id}/resolve` (D-582).

Admin only, never a moderator: it is the company's revenue (D-483), and a
claim moves Velas or money (D-580). Every call writes `audit_log`
(02-ARCHITECTURE §12).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_role
from app.core.enums import Role
from app.core.pagination import PageParams, page_params
from app.core.providers import Providers, get_providers
from app.modules.payments import claims
from app.modules.payments import service as payments_service
from app.modules.payments.rules import ClaimStatus
from app.modules.payments.schemas import (
    AdminRefundRequest,
    AdminRefundRequestPage,
    RefundRequestResolution,
    Turnover,
)
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


@router.get("/refund-requests")
async def refund_requests(
    admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
    status: Annotated[
        ClaimStatus, Query(description="The claims in this status: open if absent.")
    ] = ClaimStatus.OPEN,
) -> AdminRefundRequestPage:
    return await claims.queue(session, admin.id, status, params)


@router.post("/refund-requests/{claim_id}/resolve")
async def resolve_refund_request(
    claim_id: UUID,
    body: RefundRequestResolution,
    admin: Annotated[User, Depends(require_role(Role.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
) -> AdminRefundRequest:
    return await claims.resolve(
        session, providers.payments, admin.id, claim_id, body.action, body.note
    )
