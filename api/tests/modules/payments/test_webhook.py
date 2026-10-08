"""`POST /v1/payments/webhook` (T-8.2): verified, then credited once from the
`payments` row, never from the webhook's own amount (rule 6); a failed attempt
never sets the anchor (D-523); the bonus to the first paid purchase only
(D-522, P-380); and `raw_webhook` an allowlist (D-524). Refunds and disputes
are in test_reversals.py; captures at once in test_capture_races.py."""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, LedgerReason, PaymentStatus
from app.core.providers import FakeProviders
from app.core.providers.payments import RazorpayPayments
from app.modules.payments import rules, service
from app.modules.payments.models import Payment
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import CapturedLogs, MakeUser
from tests.modules.payments.support import (
    SIGNATURE,
    WEBHOOK,
    add_payment,
    auth,
    captured,
    deliver,
    event,
    failed,
    order,
    payment_entity,
)

pytestmark = pytest.mark.usefixtures("test_redis")

PURCHASE, BONUS = LedgerReason.PURCHASE, LedgerReason.PURCHASE_BONUS


async def _row(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    row = await db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def _ledger(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Any, int]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta)
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.reason)
    )
    return [tuple(row) for row in rows]


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return int(balance or 0)


def _lines(logs: CapturedLogs, name: str) -> list[dict[str, Any]]:
    return [dict(e) for e in logs.events if e.get("event") == name]


# --- The signature -----------------------------------------------------------------


async def _refused(response: Any) -> None:
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.critical
@pytest.mark.parametrize("signature", ["bad", "missing"])
async def test_a_bad_or_missing_signature_credits_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
    signature: str,
) -> None:
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    body = json.dumps(captured(order_id)).encode()
    headers = {"Content-Type": "application/json"}
    if signature == "bad":
        headers[SIGNATURE] = "0" * 64

    response = await client.post(WEBHOOK, content=body, headers=headers)

    await _refused(response)
    row = await _row(db, payment_id)
    assert (row.status, row.provider_payment_id, row.raw_webhook) == (
        PaymentStatus.CREATED,
        None,
        None,
    )
    assert await _ledger(db, man.id) == []
    [line] = _lines(captured_logs, "payments.webhook_refused")
    assert line["log_level"] == "warning"
    assert line["reason"] == f"{'no' if signature == 'missing' else 'bad'} signature"


@pytest.mark.critical
async def test_with_razorpay_and_no_secret_every_webhook_is_refused(
    db: AsyncSession,
    app: FastAPI,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    """Staging and production until the account exists (P-382): even a body
    signed with an empty key, what an unset secret would verify, is refused."""
    man, _ = await make_user()
    row = await add_payment(db, man.id, status=PaymentStatus.CREATED)
    app.state.providers = dataclasses.replace(
        fake_providers.as_providers(), payments=RazorpayPayments()
    )
    body = json.dumps(captured(row.provider_order_id)).encode()
    empty_key = hmac.new(b"", body, hashlib.sha256).hexdigest()

    response = await client.post(WEBHOOK, content=body, headers={SIGNATURE: empty_key})

    await _refused(response)
    assert (await _row(db, row.id)).status is PaymentStatus.CREATED
    assert await _ledger(db, man.id) == []
    assert _lines(captured_logs, "payments.webhook_secret_missing")


# --- A capture ------------------------------------------------------------------------


async def test_a_capture_pays_the_row_and_credits_its_velas(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """From the row (rule 6): pack-100's 100 Velas and its first-purchase 20.
    `paid_at` is our clock (D-523), and turnover counts it in its year."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token, "pack-100")
    at = datetime(2026, 10, 8, 9, 30, tzinfo=UTC)
    year = rules.financial_year_of(at)
    before = await service.turnover(db, year)
    clock.freeze(at)

    response = await deliver(
        client,
        fake_providers.payments,
        captured(order_id, payment_id="pay_A", amount=450_000),
    )

    assert response.status_code == 200
    assert response.json() == {}
    row = await _row(db, payment_id)
    assert row.status is PaymentStatus.PAID
    assert row.provider_payment_id == "pay_A"
    assert row.paid_at == at
    assert row.raw_webhook is not None
    assert row.raw_webhook["payment"]["id"] == "pay_A"
    assert await _ledger(db, man.id) == [(PURCHASE, 100), (BONUS, 20)]
    assert await _balance(db, man.id) == 120
    after = await service.turnover(db, year)
    assert after.turnover_paise - before.turnover_paise == 450_000
    assert after.paid_payments - before.paid_payments == 1


async def test_a_second_purchase_gets_no_bonus_and_its_poll_says_so(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    """Both ordered before either was paid, so both rows carry the bonus
    (P-380): the second capture finds the first paid, and grants none."""
    man, token = await make_user()
    _, first_order = await order(client, token)
    second, second_order = await order(client, token)
    assert (await _row(db, second)).bonus_credits == 6

    await deliver(
        client, fake_providers.payments, captured(first_order, payment_id="pay_1")
    )
    await deliver(
        client, fake_providers.payments, captured(second_order, payment_id="pay_2")
    )

    assert await _ledger(db, man.id) == [(PURCHASE, 30), (PURCHASE, 30), (BONUS, 6)]
    poll = await client.get(f"/v1/payments/{second}", headers=auth(token))
    assert poll.json() == {"status": "paid", "credits": 30, "bonus_credits": 0}
    [withheld] = _lines(captured_logs, "payments.bonus_withheld")
    assert withheld["payment_id"] == str(second)


async def test_after_a_refunded_purchase_no_bonus_either(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Money moved, then went back: still his first purchase made (D-231)."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    await add_payment(db, man.id, status=PaymentStatus.REFUNDED)

    await deliver(client, fake_providers.payments, captured(order_id))

    assert await _ledger(db, man.id) == [(PURCHASE, 30)]
    assert (await _row(db, payment_id)).bonus_credits == 0


@pytest.mark.critical
@pytest.mark.parametrize(
    "change", [{"amount": 100}, {"amount": 150_001}, {"currency": "USD"}]
)
async def test_an_amount_or_currency_not_the_rows_credits_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
    change: dict[str, Any],
) -> None:
    man, token = await make_user()
    payment_id, order_id = await order(client, token)

    response = await deliver(
        client, fake_providers.payments, captured(order_id, **change)
    )

    assert response.status_code == 200
    row = await _row(db, payment_id)
    assert row.status is PaymentStatus.FAILED
    assert row.provider_payment_id is None
    assert row.amount_paise == 150_000
    assert row.raw_webhook is not None
    assert await _ledger(db, man.id) == []
    [line] = _lines(captured_logs, "payments.amount_mismatch")
    assert line["log_level"] == "error"
    assert line["payment_id"] == str(payment_id)


async def test_another_payment_on_a_paid_order_credits_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    await deliver(
        client, fake_providers.payments, captured(order_id, payment_id="pay_1")
    )

    await deliver(
        client, fake_providers.payments, captured(order_id, payment_id="pay_2")
    )

    assert (await _row(db, payment_id)).provider_payment_id == "pay_1"
    assert await _ledger(db, man.id) == [(PURCHASE, 30), (BONUS, 6)]
    [line] = _lines(captured_logs, "payments.second_capture")
    assert line["log_level"] == "error"
    assert "T-8.3" in line["note"]


async def test_the_same_capture_again_is_a_repeat(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    clock.freeze(datetime(2026, 10, 8, 9, 30, tzinfo=UTC))
    await deliver(client, fake_providers.payments, captured(order_id))
    clock.freeze(datetime(2026, 10, 8, 9, 31, tzinfo=UTC))

    response = await deliver(client, fake_providers.payments, captured(order_id))

    assert response.status_code == 200
    assert (await _row(db, payment_id)).paid_at == datetime(
        2026, 10, 8, 9, 30, tzinfo=UTC
    )
    assert await _ledger(db, man.id) == [(PURCHASE, 30), (BONUS, 6)]


# --- Attempts: one order, several payments (D-523) -------------------------------------


@pytest.mark.critical
async def test_a_failed_attempt_then_a_capture_is_paid_and_credited(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """A UPI retry: Razorpay's own example. The failure never set the anchor,
    so the capture isn't taken for a repeat."""
    man, token = await make_user()
    payment_id, order_id = await order(client, token)

    await deliver(client, fake_providers.payments, failed(order_id, payment_id="pay_1"))
    row = await _row(db, payment_id)
    assert (row.status, row.provider_payment_id) == (PaymentStatus.FAILED, None)
    await deliver(
        client, fake_providers.payments, captured(order_id, payment_id="pay_2")
    )

    row = await _row(db, payment_id)
    assert (row.status, row.provider_payment_id) == (PaymentStatus.PAID, "pay_2")
    assert await _ledger(db, man.id) == [(PURCHASE, 30), (BONUS, 6)]


async def test_a_failed_event_after_the_capture_changes_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    man, token = await make_user()
    payment_id, order_id = await order(client, token)
    await deliver(
        client, fake_providers.payments, captured(order_id, payment_id="pay_2")
    )
    before = (await _row(db, payment_id)).raw_webhook

    await deliver(client, fake_providers.payments, failed(order_id, payment_id="pay_1"))

    row = await _row(db, payment_id)
    assert (row.status, row.provider_payment_id) == (PaymentStatus.PAID, "pay_2")
    assert row.raw_webhook == before
    assert await _balance(db, man.id) == 36


# --- What it answers -----------------------------------------------------------------


async def test_an_unknown_order_is_answered_and_logged(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    response = await deliver(
        client, fake_providers.payments, captured("order_nobody_made")
    )

    assert response.status_code == 200
    [line] = _lines(captured_logs, "payments.webhook_unknown_order")
    assert line["order_id"] == "order_nobody_made"


@pytest.mark.parametrize(
    "name",
    ["payment.authorized", "payment.pending", "refund.speed_changed", "order.paid"],
)
async def test_an_event_it_doesnt_handle_is_answered_and_ignored(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
    name: str,
) -> None:
    _, token = await make_user()
    payment_id, order_id = await order(client, token)

    response = await deliver(
        client, fake_providers.payments, event(name, payment=payment_entity(order_id))
    )

    assert response.status_code == 200
    assert (await _row(db, payment_id)).status is PaymentStatus.CREATED
    [line] = _lines(captured_logs, "payments.webhook_ignored")
    assert line["webhook_event"] == name


@pytest.mark.critical
async def test_a_womans_payment_is_never_credited(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    """She can't order (D-076), so her row is written straight to the table:
    the service refuses before the wallet and the database would."""
    woman, _ = await make_user(Gender.FEMALE)
    row = await add_payment(db, woman.id, status=PaymentStatus.CREATED)

    response = await deliver(
        client, fake_providers.payments, captured(row.provider_order_id)
    )

    assert response.status_code == 200
    paid = await _row(db, row.id)
    assert (paid.status, paid.provider_payment_id) == (PaymentStatus.FAILED, None)
    assert await _ledger(db, woman.id) == []
    [line] = _lines(captured_logs, "payments.not_a_man")
    assert line["log_level"] == "error"
    assert "refund it by hand" in line["note"]


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b'{"payload": {}}',
        json.dumps({"event": "payment.captured", "payload": {}}).encode(),
        json.dumps(captured("order_x", amount="150000")).encode(),
        json.dumps(captured("order_x", amount=True)).encode(),
    ],
    ids=[
        "text",
        "a-list",
        "no-event",
        "no-payment",
        "amount-a-string",
        "amount-a-bool",
    ],
)
async def test_signed_but_unreadable_is_a_500_so_razorpay_retries(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
    body: bytes,
) -> None:
    signed = fake_providers.payments.sign(body)

    response = await client.post(
        WEBHOOK, content=signed.body, headers={SIGNATURE: signed.signature}
    )

    assert response.status_code == 500
    assert _lines(captured_logs, "payments.webhook_unreadable")


# --- `raw_webhook`: an allowlist (D-524) -------------------------------------------------

PAYER = {
    "email": "payer@example.com",
    "contact": "+919812345678",
    "vpa": "payer@okbank",
    "card_id": "card_PAYER",
    "card": {"last4": "4242", "network": "Visa"},
    "bank": "HDFC",
    "wallet": "paytm",
    "acquirer_data": {"rrn": "RRN-PAYER", "upi_transaction_id": "UPI-PAYER"},
    "notes": {"address": "PAYER-ADDRESS"},
    "description": "PAYER-DESCRIPTION",
    "fee": 3540,
    "tax": 540,
    "a_field_razorpay_adds_in_2031": "FUTURE-FIELD",
}


@pytest.mark.critical
async def test_raw_webhook_keeps_exactly_the_allowlisted_fields(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    captured_logs: CapturedLogs,
) -> None:
    """Every payer field set, and one nobody has listed: only the allowlist is
    stored, and none of it reaches a log (rule 15)."""
    _, token = await make_user()
    payment_id, order_id = await order(client, token)
    body = captured(order_id, payment_id="pay_A", **PAYER)
    body["a_top_level_field_from_2031"] = "FUTURE-TOP"

    await deliver(client, fake_providers.payments, body)

    raw = (await _row(db, payment_id)).raw_webhook
    assert raw == {
        "event": "payment.captured",
        "created_at": 1_759_900_100,
        "payment": {
            "id": "pay_A",
            "order_id": order_id,
            "amount": 150_000,
            "currency": "INR",
            "status": "captured",
            "method": "upi",
            "error_code": None,
            "created_at": 1_759_900_000,
        },
    }
    for value in (
        "payer@example.com",
        "+919812345678",
        "9812345678",
        "payer@okbank",
        "PAYER",
        "4242",
        "FUTURE",
    ):
        assert value not in captured_logs.text
    captured_logs.assert_listening()
