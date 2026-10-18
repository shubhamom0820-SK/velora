"""Test-only routes, each mounted by `create_app()` only beside the fake it
reads or drives, and only where `ENV` is local: allowlists both (rule 16). None
is ever in OpenAPI, so `make types` is the same everywhere; 04-API lists them
under "Local only".

- `router`: the code the fake SMS provider last sent a number (T-3.13), where
  `SMS_PROVIDER` is fake. Playwright reads sign-in codes here (06-TESTING).
  Beside it, behind the same gate, a Thread's hour run out now (T-7.13,
  D-930): J7's expiry, without moving any clock.
- `payments_router`: the fake gateway's webhook for a payment, delivered to the
  API's own webhook route (T-8.1), where `PAYMENTS_PROVIDER` is fake. It stands
  in for Razorpay locally: a fake order is paid by calling it.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.e2e import service
from app.modules.e2e.schemas import (
    ExpiredThread,
    LastCode,
    LastCodeQuery,
    SimulatedWebhook,
    SimulateWebhook,
)

router = APIRouter(prefix="/test", tags=["test"], include_in_schema=False)
payments_router = APIRouter(prefix="/test", tags=["test"], include_in_schema=False)


@router.post("/sms/last-code")
async def sms_last_code(body: LastCodeQuery, request: Request) -> LastCode:
    return LastCode(code=service.last_code(request.app.state.providers.sms, body.phone))


@router.post("/threads/{thread_id}/expire")
async def expire_thread(
    thread_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExpiredThread:
    return ExpiredThread(expires_at=await service.expire_thread(session, thread_id))


@payments_router.post("/payments/webhook")
async def payments_webhook(
    body: SimulateWebhook,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SimulatedWebhook:
    status = await service.simulate_webhook(
        request.app,
        session,
        request.app.state.providers.payments,
        payment_id=body.payment_id,
        outcome=body.outcome,
        amount_paise=body.amount_paise,
    )
    return SimulatedWebhook(delivered_status=status)
