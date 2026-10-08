"""Local-only stand-ins for the outside world, for the E2E and local
development: what the fake SMS provider has 'sent' (T-3.13), and the webhook
the fake gateway would send (T-8.1). No rules of their own."""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.providers.payments import FakePayments, Outcome, PaymentsProvider
from app.core.providers.sms import FakeSms, SmsProvider
from app.core.security import normalize_phone
from app.modules.payments import service as payments_service

# Where Razorpay delivers its webhooks, and the header it signs them in (T-8.2).
WEBHOOK_PATH = "/v1/payments/webhook"
SIGNATURE_HEADER = "X-Razorpay-Signature"


def last_code(sms: SmsProvider, typed_phone: str) -> str | None:
    """The last code `sms` sent to the number, typed as a person would type it.

    The fake's own outbox, never the stored code: a number the API sent nothing
    to, a banned one (D-073), gets no code here, exactly as its phone wouldn't.
    """
    if not isinstance(sms, FakeSms):
        # create_app() mounts this only beside the fake; anything else is a bug.
        raise AppError("NOT_FOUND", "Not found.", status=404)
    return sms.last_code(normalize_phone(typed_phone))


async def simulate_webhook(
    app: FastAPI,
    session: AsyncSession,
    payments: PaymentsProvider,
    *,
    payment_id: UUID,
    outcome: Outcome,
    amount_paise: int | None,
) -> int:
    """Deliver the fake gateway's signed webhook for a payment to this app's own
    webhook route, in process, as Razorpay would over the network, and return
    the status it answered. Built from the `payments` row, so it works for an
    order made before the API last restarted. T-8.2's route answers it as it
    answers Razorpay.
    """
    if not isinstance(payments, FakePayments):
        # create_app() mounts this only beside the fake; anything else is a bug.
        raise AppError("NOT_FOUND", "Not found.", status=404)
    order = await payments_service.order_of(session, payment_id)
    if order is None:
        raise AppError("NOT_FOUND", "No such payment.", status=404)
    order_id, order_amount = order
    webhook = payments.webhook(
        outcome,
        order_id=order_id,
        amount_paise=order_amount if amount_paise is None else amount_paise,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://local"
    ) as client:
        response = await client.post(
            WEBHOOK_PATH,
            content=webhook.body,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: webhook.signature,
            },
        )
    return response.status_code
