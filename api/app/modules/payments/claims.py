"""A broken payment's claim (T-8.3, D-580): `POST /v1/refund-requests`, and the
admin's `GET /v1/admin/refund-requests` and `POST .../{id}/resolve`.

**A claim is a broken payment, never a change of mind** (D-050, D-230):
`missing_velas`, the money went through and no Velas came, or
`duplicate_charge`, charged twice for one purchase. Purchases are final.

**Filing:** the caller's own payment, or `NOT_FOUND`, the same for someone
else's as for none. `missing_velas` on a payment whose Velas were granted
(`paid`, `refunded`) is `NOT_ALLOWED`. One open claim per payment, held by a
partial unique index: a second is `ALREADY_EXISTS`.

**Resolving: the gateway decides what can be done, never the claim's kind or
the admin's word** (rule 6). The claim's row is locked for the whole
resolution, so two admins at once take turns. Before anything moves, the
gateway is asked for every payment on the order (`order_payments`), outside
any payment row's or wallet's lock (D-077):

- **grant:** while the row has credited nothing (no anchor), the first
  captured, untouched payment for exactly the order's amount is captured
  through the webhook's own path: `purchase` and, by D-522's rule,
  `purchase_bonus`, under the webhook's own key (D-077), **never
  `admin_grant`**. A webhook arriving later is a repeat.
- **refund:** a captured, untouched payment no Velas can ever stand against
  (D-076 rule 3): never the credited one, and never one a grant could credit,
  whose fix is the grant. It is returned in full in the gateway, with the
  claim's id as the receipt, which Razorpay takes once. The record is the
  claim's (`refunded`, the gateway's payment and refund ids): the payment
  returned has no row of its own, and the credited payment's row is never
  touched, so turnover stays right (D-483, D-580). Its `refund.created` then
  reaches the webhook, which finds it isn't the credited payment and takes
  nothing.
- **reject:** nothing broken, a note saying why. Two orders both credited
  ("I bought twice") are rejected: both purchases completed (D-230).

Every list and every resolution writes `audit_log`. Logs name the claim, the
payment and the order: never the payer, never the admin's note (rule 15).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.core.providers.payments import (
    PaymentsProvider,
    PaymentsUnavailable,
    ProviderPayment,
)
from app.modules.admin import service as admin_service
from app.modules.payments import repository, rules, webhooks
from app.modules.payments.models import Payment, RefundRequest
from app.modules.payments.repository import MONEY_MOVED, ClaimRow
from app.modules.payments.rules import ClaimAction, ClaimReason, ClaimStatus
from app.modules.payments.schemas import (
    AdminRefundRequest,
    AdminRefundRequestPage,
    RefundRequestView,
)
from app.modules.users.models import User

log = structlog.get_logger(__name__)

# The admin's queue, by `(created_at, id)` (D-270).
CLAIMS_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


def _not_allowed(message: str, why: str) -> AppError:
    return AppError("NOT_ALLOWED", message, status=422, details={"why": why})


def _unavailable() -> AppError:
    return AppError(
        "PROVIDER_UNAVAILABLE",
        "The payment gateway isn't answering. Try again in a few minutes.",
        status=503,
    )


# --- Filing ---------------------------------------------------------------------------


async def file(
    session: AsyncSession, user: User, payment_id: UUID, reason: ClaimReason
) -> RefundRequestView:
    """`POST /refund-requests`: an open claim on the caller's own payment."""
    async with session.begin():
        payment = await repository.payment_by_id(session, payment_id)
        if payment is None or payment.user_id != user.id:
            raise AppError("NOT_FOUND", "No such payment.", status=404)
        if reason is ClaimReason.MISSING_VELAS and payment.status in MONEY_MOVED:
            raise _not_allowed(
                "This payment's Velas reached your balance.", "velas_granted"
            )
        claim = await repository.add_claim(
            session, user_id=user.id, payment_id=payment.id, reason=reason
        )
        if claim is None:
            raise AppError(
                "ALREADY_EXISTS",
                "This payment already has a claim we're looking at.",
                status=409,
            )
        view = RefundRequestView(
            id=claim.id,
            payment_id=claim.payment_id,
            reason=ClaimReason(claim.reason),
            status=ClaimStatus(claim.status),
            created_at=claim.created_at,
        )
    log.info(
        "claims.filed",
        claim_id=str(view.id),
        payment_id=str(view.payment_id),
        reason=str(reason),
    )
    return view


# --- The admin's -----------------------------------------------------------------------


async def queue(
    session: AsyncSession, admin_id: UUID, status: ClaimStatus, params: PageParams
) -> AdminRefundRequestPage:
    """`GET /admin/refund-requests`: claims in `status`, oldest first, audited."""
    after = None if params.cursor is None else CLAIMS_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.claims_page(
            session, status=status, after=after, limit=params.fetch
        )
        await admin_service.audit(
            session, admin_id, "refund_requests.list", {"status": str(status)}
        )
    return AdminRefundRequestPage.of(
        [_admin_view(row) for row in rows],
        params,
        lambda claim: CLAIMS_CURSOR.encode((claim.created_at, claim.id)),
    )


async def resolve(
    session: AsyncSession,
    payments: PaymentsProvider,
    admin_id: UUID,
    claim_id: UUID,
    action: ClaimAction,
    note: str | None,
) -> AdminRefundRequest:
    """`POST /admin/refund-requests/{id}/resolve`, in one transaction under
    the claim's lock: refused, nothing has changed."""
    if action is ClaimAction.REJECT and note is None:
        raise AppError(
            "VALIDATION_ERROR", "A rejection says why, in its note.", status=400
        )
    async with session.begin():
        claim = await repository.lock_claim(session, claim_id)
        if claim is None:
            raise AppError("NOT_FOUND", "No such claim.", status=404)
        if claim.status != ClaimStatus.OPEN:
            raise _not_allowed("This claim is resolved already.", "resolved")
        payment = await repository.payment_by_id(session, claim.payment_id)
        assert payment is not None  # a foreign key, RESTRICT
        if action is ClaimAction.REJECT:
            _close(claim, ClaimStatus.REJECTED, note=note)
        elif action is ClaimAction.GRANT:
            await _grant(session, payments, claim, payment, note)
        else:
            await _refund(payments, claim, payment, note)
        await admin_service.audit(
            session,
            admin_id,
            "refund_requests.resolve",
            {
                "refund_request_id": str(claim.id),
                "action": str(action),
                "status": claim.status,
                "provider_payment_id": claim.provider_payment_id,
                "provider_refund_id": claim.provider_refund_id,
            },
        )
        await session.flush()
        row = await repository.claim_with_payment(session, claim.id)
        assert row is not None
    log.info(
        "claims.resolved",
        claim_id=str(claim.id),
        payment_id=str(payment.id),
        order_id=payment.provider_order_id,
        action=str(action),
        status=claim.status,
    )
    return _admin_view(row)


async def _held(payments: PaymentsProvider, payment: Payment) -> list[ProviderPayment]:
    """What the gateway holds on the order: the only evidence a resolution
    acts on."""
    try:
        return await payments.order_payments(payment.provider_order_id)
    except PaymentsUnavailable as refusal:
        log.warning("claims.gateway_unavailable", reason=str(refusal))
        raise _unavailable() from None


async def _grant(
    session: AsyncSession,
    payments: PaymentsProvider,
    claim: RefundRequest,
    payment: Payment,
    note: str | None,
) -> None:
    held = await _held(payments, payment)
    # The row's lock, then the wallet's, only after the gateway has answered.
    row = await repository.lock_payment(session, order_id=payment.provider_order_id)
    assert row is not None
    if row.provider_payment_id is not None:
        raise _not_allowed("This payment's Velas were granted already.", "credited")
    found = rules.grantable(held, anchor=None, amount_paise=row.amount_paise)
    if found is None:
        raise _not_allowed(
            "The gateway holds no captured payment for this order's amount.",
            "nothing_to_grant",
        )
    outcome = await webhooks.capture_from_gateway(session, row, found)
    if outcome is not webhooks.Outcome.CAPTURED:
        raise _not_allowed("The capture credited nothing.", str(outcome))
    _close(claim, ClaimStatus.GRANTED, note=note, provider_payment_id=found.id)


async def _refund(
    payments: PaymentsProvider,
    claim: RefundRequest,
    payment: Payment,
    note: str | None,
) -> None:
    held = await _held(payments, payment)
    found = rules.refundable(
        held, anchor=payment.provider_payment_id, amount_paise=payment.amount_paise
    )
    if found is None:
        raise _not_allowed(
            "The gateway holds no charge on this order that can go back: none "
            "captured beside the one credited, or one that should be granted.",
            "nothing_to_refund",
        )
    try:
        refund = await payments.refund(
            payment_id=found.id, amount_paise=found.amount_paise, receipt=str(claim.id)
        )
    except PaymentsUnavailable as refusal:
        log.warning("claims.refund_unavailable", reason=str(refusal))
        raise _unavailable() from None
    _close(
        claim,
        ClaimStatus.REFUNDED,
        note=note,
        provider_payment_id=found.id,
        provider_refund_id=refund.id,
    )


def _close(
    claim: RefundRequest,
    status: ClaimStatus,
    *,
    note: str | None,
    provider_payment_id: str | None = None,
    provider_refund_id: str | None = None,
) -> None:
    claim.status = status
    claim.note = note
    claim.provider_payment_id = provider_payment_id
    claim.provider_refund_id = provider_refund_id
    claim.resolved_at = clock.now()


def _admin_view(row: ClaimRow) -> AdminRefundRequest:
    claim, order_id, payment_status = row
    return AdminRefundRequest(
        id=claim.id,
        user_id=claim.user_id,
        payment_id=claim.payment_id,
        order_id=order_id,
        payment_status=payment_status,
        reason=ClaimReason(claim.reason),
        status=ClaimStatus(claim.status),
        note=claim.note,
        provider_payment_id=claim.provider_payment_id,
        provider_refund_id=claim.provider_refund_id,
        created_at=claim.created_at,
        resolved_at=claim.resolved_at,
    )
