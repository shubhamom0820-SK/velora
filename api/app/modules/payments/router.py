"""`GET /v1/packs` and `POST /v1/payments/orders` (T-8.1), for men once
onboarding is done; a woman is refused both, `NOT_ALLOWED` (D-076).
`POST /v1/payments/webhook` and `GET /v1/payments/{id}` (T-8.2).

`GET /packs` reads and writes nothing else, so `current_user`'s 300 a minute is
its only limit. An order asks the gateway for one, so it has its own: 20 an hour
per man, room for every retry a real checkout needs (02-ARCHITECTURE §12).

The webhook's auth is its signature, checked before anything is read, and it has
no rate limit: every request is verified, a limit would slow Razorpay's retries
of the real ones, and a flood is the edge's to stop (02-ARCHITECTURE §12). The
body is read raw, as Razorpay signs it (rule 8: parse, then call).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.deps import app_settings, onboarded_user, user_rate_limit
from app.core.providers import Providers, get_providers
from app.modules.payments import rules, service, webhooks
from app.modules.payments.schemas import (
    Order,
    OrderRequest,
    Pack,
    PaymentStatusView,
    WebhookReceived,
)
from app.modules.users.models import User

ORDERS_PER_HOUR = 20

router = APIRouter(tags=["payments"])


@router.get("/packs")
async def list_packs(
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Pack]:
    return await service.packs_for(session, user)


@router.post(
    "/payments/orders",
    dependencies=[
        Depends(user_rate_limit("payment_orders", limit=ORDERS_PER_HOUR, window_s=3600))
    ],
)
async def create_order(
    body: OrderRequest,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", pattern=rules.IDEMPOTENCY_KEY_PATTERN)
    ],
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    settings: Annotated[Settings, Depends(app_settings)],
) -> Order:
    return await service.create_order(
        session,
        user,
        providers.payments,
        pack_id=body.pack_id,
        key=idempotency_key,
        gst_registered=settings.GST_REGISTERED,
    )


@router.post("/payments/webhook")
async def payments_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[Providers, Depends(get_providers)],
    signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
) -> WebhookReceived:
    await webhooks.receive(session, providers.payments, await request.body(), signature)
    return WebhookReceived()


@router.get("/payments/{payment_id}")
async def payment_status(
    payment_id: UUID,
    user: Annotated[User, Depends(onboarded_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentStatusView:
    return await service.status_of(session, user, payment_id)
