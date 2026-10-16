"""`/v1/admin/*` (04-API.md). T-8.1 built the first, `GET /admin/turnover`;
T-8.3 the claims, `GET /admin/refund-requests` and
`POST /admin/refund-requests/{id}/resolve` (D-582); T-9.5 the panel's.

**Every route carries its own `require_role`** (P-30): the web's `/admin`
gate is UX, and the API's role check is the only thing guarding admin data
(D-024). Turnover, claims and Velas are an admin's alone, never a moderator's:
revenue (D-483), and a claim or a grant moves Velas or money (D-580, D-923).
The panel's other routes take either, and `admin.panel` refuses a moderator
what only an admin may do (D-922). Every call writes `audit_log`
(02-ARCHITECTURE §12).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, require_role
from app.core.enums import ReportStatus, Role
from app.core.pagination import PageParams, page_params
from app.core.providers import Providers, get_providers
from app.core.queue import Queue, get_queue
from app.modules.admin import panel, schemas
from app.modules.admin.rules import REASON_MAX, REASON_MIN, STAFF
from app.modules.payments import claims
from app.modules.payments import rules as payments_rules
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


# --- The panel (T-9.5) ------------------------------------------------------------------

Staff = Annotated[User, Depends(require_role(*STAFF))]
Admin = Annotated[User, Depends(require_role(Role.ADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]
Params = Annotated[PageParams, Depends(page_params)]


@router.get("/metrics")
async def metrics(staff: Staff, session: Session) -> schemas.AdminMetrics:
    return await panel.metrics(session, staff)


@router.get("/users")
async def users(
    staff: Staff,
    session: Session,
    params: Params,
    settings: Annotated[Settings, Depends(app_settings)],
    q: Annotated[
        str | None,
        Query(
            max_length=64,
            description="A whole number, an id, or a name's or username's start.",
        ),
    ] = None,
) -> schemas.AdminUserPage:
    return await panel.users(session, staff, q, params, settings)


@router.get("/users/{user_id}")
async def user_detail(
    user_id: UUID,
    staff: Staff,
    session: Session,
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> schemas.AdminUserDetail:
    return await panel.user_detail(
        session, staff, user_id, storage=providers.storage, settings=settings
    )


@router.post("/users/{user_id}/status", status_code=204)
async def set_status(
    user_id: UUID, body: schemas.StatusChange, staff: Staff, session: Session
) -> Response:
    await panel.set_status(session, staff, user_id, body.status, body.reason)
    return Response(status_code=204)


@router.post("/users/{user_id}/credits", status_code=204)
async def change_credits(
    user_id: UUID,
    body: schemas.CreditsChange,
    admin: Admin,
    session: Session,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", pattern=payments_rules.IDEMPOTENCY_KEY_PATTERN),
    ],
) -> Response:
    await panel.change_credits(
        session, admin, user_id, body.delta, body.reason, idempotency_key
    )
    return Response(status_code=204)


@router.get("/reports")
async def reports(
    staff: Staff,
    session: Session,
    params: Params,
    status: Annotated[
        ReportStatus, Query(description="The reports in this status: open if absent.")
    ] = ReportStatus.OPEN,
) -> schemas.AdminReportPage:
    return await panel.reports(session, staff, status, params)


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve_report(
    report_id: UUID, body: schemas.ReportResolution, staff: Staff, session: Session
) -> Response:
    await panel.resolve_report(session, staff, report_id, body.action, body.note)
    return Response(status_code=204)


@router.get("/moderation")
async def moderation(
    staff: Staff,
    session: Session,
    params: Params,
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> schemas.AdminPhotoPage:
    return await panel.moderation(
        session, staff, params, storage=providers.storage, settings=settings
    )


@router.post("/photos/{photo_id}/decide", status_code=204)
async def decide_photo(
    photo_id: UUID,
    body: schemas.PhotoDecision,
    staff: Staff,
    session: Session,
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
    queue: Annotated[Queue, Depends(get_queue)],
) -> Response:
    await panel.decide_photo(
        session,
        staff,
        photo_id,
        body.approve,
        body.reason,
        body.note,
        storage=providers.storage,
        settings=settings,
        queue=queue,
    )
    return Response(status_code=204)


@router.get("/threads/{thread_id}/messages")
async def thread_messages(
    thread_id: UUID,
    staff: Staff,
    session: Session,
    params: Params,
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
    reason: Annotated[
        str,
        Query(
            min_length=REASON_MIN,
            max_length=REASON_MAX,
            description="Why staff read this Thread: kept in audit_log (D-924).",
        ),
    ],
) -> schemas.AdminMessagePage:
    return await panel.thread_messages(
        session,
        staff,
        thread_id,
        reason,
        params,
        storage=providers.storage,
        settings=settings,
    )


@router.get("/audit")
async def audit_log(
    staff: Staff,
    session: Session,
    params: Params,
    action: Annotated[
        str | None, Query(min_length=1, max_length=64, description="Only this action.")
    ] = None,
) -> schemas.AuditEntryPage:
    return await panel.audit_entries(session, staff, action, params)


@router.get("/freezes")
async def freezes(
    staff: Staff, session: Session, params: Params
) -> schemas.AdminFreezePage:
    return await panel.freezes(session, staff, params)
