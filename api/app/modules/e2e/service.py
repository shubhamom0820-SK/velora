"""Local-only stand-ins for the outside world, for the E2E and local
development: what the fake SMS provider has 'sent' (T-3.13), the webhook the
fake gateway would send (T-8.1), an hour that has passed (T-7.13, D-930), and
a staff role for the E2E's walk of the admin screens (T-9.11, D-963).
No rules of their own."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Role, ThreadStatus
from app.core.errors import AppError
from app.core.providers.payments import FakePayments, Outcome, PaymentsProvider
from app.core.providers.sms import FakeSms, SmsProvider
from app.core.security import normalize_phone
from app.modules.admin import service as admin_service
from app.modules.payments import service as payments_service
from app.modules.threads import repository as threads_repository
from app.modules.users import repository as users_repository

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


async def expire_thread(session: AsyncSession, thread_id: UUID) -> datetime:
    """Let a Thread's hour run out now (D-930): its `expires_at`, the one column
    the hour lives in (D-560), set to this instant, its row held as everything
    that moves the hour holds it. Expired is `expires_at <= now` for the API,
    the sweep and the browser alike, so each sees it run out by its own clock
    from here on. Never earlier: a message sent a moment before would then
    read as written after the hour ran out (the E2E's voice note did, 0.85 s
    before a one-second-early hour). The status is left to the worker's
    sweep, as when an hour passes, and nothing else moves.

    Only a Thread with an hour: an active one with `expires_at`. A Knot or a
    private message has none to run out (D-003, D-550), and an expired one has
    already run out; each is `NOT_FOUND`, as no Thread is, and nothing changes.
    """
    async with session.begin():
        thread = await threads_repository.lock(session, thread_id)
        if (
            thread is None
            or thread.status is not ThreadStatus.ACTIVE
            or thread.expires_at is None
        ):
            raise AppError("NOT_FOUND", "No such Thread with an hour.", status=404)
        thread.expires_at = clock.now()
        return thread.expires_at


async def make_staff(session: AsyncSession, user_id: UUID, role: Role) -> Role:
    """Make a person staff (D-963): T-9.11's walk of the admin screens, which
    render only for a moderator or an admin, and the E2E has no other way to
    make one. `role` is moderator or admin, never user (the schema refuses
    it). The row is locked, as everything that changes a user locks it, and
    the change is an `audit_log` row in the same transaction, as any role
    change must be: the system user its actor (D-905), nobody having made it.

    An account that doesn't exist, or was erased, is `NOT_FOUND`.
    """
    async with session.begin():
        user = await users_repository.user_for_update(session, user_id)
        if user is None or user.anonymised_at is not None:
            raise AppError("NOT_FOUND", "No such account.", status=404)
        was = user.role
        user.role = role
        await admin_service.audit(
            session,
            admin_service.SYSTEM_USER_ID,
            "user.role",
            {"from": str(was), "to": str(role), "by": "e2e"},
            target=("user", user_id),
        )
        return user.role
