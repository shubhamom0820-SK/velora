"""Razorpay's orders over httpx (T-8.1), against a mock transport: no keys, no
network. Built to Razorpay's Orders API as documented (read 8 October 2026);
no call has reached Razorpay itself yet (P-0.8). And its webhook signature
(T-8.2): the hex HMAC-SHA256 of the raw body, keyed by the webhook secret."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import httpx
import pytest

from app.core.config import Settings
from app.core.providers import build_providers
from app.core.providers.payments import (
    PaymentsUnavailable,
    ProviderOrder,
    RazorpayPayments,
)
from tests.conftest import CapturedLogs, make_test_settings

# Recognisable, and never real: the repo's test keys are public (D-060).
KEY_ID = "rzp_test_notarealkey0"
KEY_SECRET = "not-a-real-secret-velora-test"


def _razorpay(handler: httpx.MockTransport) -> RazorpayPayments:
    return RazorpayPayments(KEY_ID, KEY_SECRET, transport=handler)


def _answering(
    status: int, body: object
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle), seen


RECEIPT = "0b6f5c1e-1d0b-4a0e-9a59-7b3c4d2a1f00"
ORDER = {
    "id": "order_RB58MiP5SPFYyM",
    "entity": "order",
    "amount": 150_000,
    "amount_paid": 0,
    "amount_due": 150_000,
    "currency": "INR",
    "receipt": RECEIPT,
    "status": "created",
    "attempts": 0,
    "notes": {},
    "created_at": 1_759_900_000,
}


async def test_an_order_is_posted_as_razorpay_documents_it() -> None:
    transport, seen = _answering(200, ORDER)
    payments = _razorpay(transport)

    order = await payments.create_order(amount_paise=150_000, receipt=RECEIPT)
    await payments.aclose()

    assert order == ProviderOrder(id="order_RB58MiP5SPFYyM", amount_paise=150_000)
    [request] = seen
    assert request.method == "POST"
    assert str(request.url) == "https://api.razorpay.com/v1/orders"
    assert json.loads(request.content) == {
        "amount": 150_000,
        "currency": "INR",
        "receipt": RECEIPT,
    }
    expected = base64.b64encode(f"{KEY_ID}:{KEY_SECRET}".encode()).decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    assert KEY_SECRET not in str(request.url)


@pytest.mark.parametrize("status", [400, 401, 429, 500, 503])
async def test_a_refusal_is_unavailable_naming_the_status(status: int) -> None:
    transport, _ = _answering(
        status, {"error": {"code": "BAD_REQUEST_ERROR", "description": "no"}}
    )

    with pytest.raises(PaymentsUnavailable, match=f"HTTP {status}"):
        await _razorpay(transport).create_order(amount_paise=150_000, receipt="r")


async def test_no_answer_is_unavailable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(PaymentsUnavailable, match="ConnectTimeout"):
        await _razorpay(httpx.MockTransport(handle)).create_order(
            amount_paise=150_000, receipt="r"
        )


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        {"entity": "order"},
        {**ORDER, "id": None},
        {**ORDER, "id": "pay_123"},
        {**ORDER, "amount": 100},
        {**ORDER, "currency": "USD"},
    ],
    ids=["text", "no-id", "null-id", "not-an-order", "other-amount", "other-currency"],
)
async def test_an_answer_that_isnt_our_order_is_never_trusted(body: object) -> None:
    transport, _ = _answering(200, body)

    with pytest.raises(PaymentsUnavailable):
        await _razorpay(transport).create_order(amount_paise=150_000, receipt="r")


@pytest.mark.parametrize(
    ("key_id", "secret"), [("", ""), (KEY_ID, ""), ("", KEY_SECRET)]
)
async def test_without_keys_it_refuses_and_calls_nobody(
    key_id: str, secret: str
) -> None:
    """Staging and production run Razorpay, and without an account (P-0.8)
    they can have no keys: each order is refused, the API still starts
    (P-382)."""
    transport, seen = _answering(200, ORDER)

    with pytest.raises(PaymentsUnavailable, match="P-382"):
        await RazorpayPayments(key_id, secret, transport=transport).create_order(
            amount_paise=150_000, receipt="r"
        )
    assert seen == []


async def test_its_messages_never_carry_a_key(captured_logs: CapturedLogs) -> None:
    transport, _ = _answering(401, {"error": {"description": f"bad key {KEY_ID}"}})

    with pytest.raises(PaymentsUnavailable) as refusal:
        await _razorpay(transport).create_order(amount_paise=150_000, receipt="r")

    assert KEY_SECRET not in str(refusal.value)
    assert KEY_ID not in str(refusal.value)
    assert KEY_SECRET not in captured_logs.text
    captured_logs.assert_listening()


def test_the_public_key_is_the_settings() -> None:
    settings: Settings = make_test_settings().model_copy(
        update={
            "PAYMENTS_PROVIDER": "razorpay",
            "RAZORPAY_KEY_ID": KEY_ID,
            "RAZORPAY_KEY_SECRET": KEY_SECRET,
        }
    )

    assert build_providers(settings).payments.key_id == KEY_ID


# --- The webhook's signature (T-8.2) ------------------------------------------------

WEBHOOK_SECRET = "not-a-real-webhook-secret-velora-test"
BODY = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_1"}}}}'


def _signature(secret: str, body: bytes) -> str:
    """Computed here, as Razorpay documents it, not by the code under test."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _verifier(secret: str = WEBHOOK_SECRET) -> RazorpayPayments:
    return RazorpayPayments(KEY_ID, KEY_SECRET, webhook_secret=secret)


def test_a_webhook_signed_with_the_secret_is_verified() -> None:
    assert _verifier().verify_webhook(BODY, _signature(WEBHOOK_SECRET, BODY)) is True


@pytest.mark.parametrize(
    "signature",
    [
        _signature("another-secret", BODY),
        _signature(WEBHOOK_SECRET, BODY + b" "),
        _signature(WEBHOOK_SECRET, BODY).upper(),
        "",
        "not hex at all",
        "\u00e9\u00e9",
    ],
    ids=["other-secret", "other-body", "upper-case", "empty", "not-hex", "not-ascii"],
)
def test_any_other_signature_is_refused(signature: str) -> None:
    """The raw body, byte for byte: re-serialised JSON would be another body."""
    assert _verifier().verify_webhook(BODY, signature) is False


@pytest.mark.critical
def test_without_the_secret_every_signature_is_refused_naming_the_setting(
    captured_logs: CapturedLogs,
) -> None:
    """Even one made with an empty key, which is what an unset secret would
    verify if it were used (P-382)."""
    verifier = _verifier(secret="")

    assert verifier.verify_webhook(BODY, _signature("", BODY)) is False
    [line] = [e for e in captured_logs.events if e.get("event") != "rule15_probe"]
    assert line["event"] == "payments.webhook_secret_missing"
    assert line["log_level"] == "error"
    assert "RAZORPAY_WEBHOOK_SECRET" in line["note"]
    assert WEBHOOK_SECRET not in captured_logs.text
    captured_logs.assert_listening()


def test_the_webhook_secret_is_the_settings() -> None:
    settings: Settings = make_test_settings().model_copy(
        update={
            "PAYMENTS_PROVIDER": "razorpay",
            "RAZORPAY_WEBHOOK_SECRET": WEBHOOK_SECRET,
        }
    )
    payments = build_providers(settings).payments

    assert payments.verify_webhook(BODY, _signature(WEBHOOK_SECRET, BODY)) is True
