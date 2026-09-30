"""Payments: Razorpay orders and webhooks (D-026, T-8.1, T-8.2).

Credits are granted only by a verified webhook. The fake signs its webhooks
with HMAC-SHA256 of the raw body, as Razorpay does, so the webhook route runs
the same verification code in tests as in production.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderOrder:
    id: str
    amount_paise: int
    currency: str = "INR"


@dataclass(frozen=True)
class SignedWebhook:
    """A webhook exactly as it would arrive: the raw body and its signature header."""

    body: bytes
    signature: str


class PaymentsProvider(Protocol):
    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder:
        """Create the gateway's order; `receipt` is our own reference for it."""
        ...

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        """True only if `signature` is the gateway's signature of the raw `body`."""
        ...


def _sign(secret: bytes, body: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


class FakePayments:
    """Orders in memory, and webhooks signed with a fixed local secret.

    `capture(order_id)` and `fail(order_id)` build the webhook the gateway
    would send, for a test (or T-8.1's local-only simulator) to deliver.
    """

    _secret = b"fake-payments-local-only"

    def __init__(self) -> None:
        self.orders: dict[str, ProviderOrder] = {}
        self._payments = 0

    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder:
        order = ProviderOrder(
            id=f"order_fake_{len(self.orders) + 1}", amount_paise=amount_paise
        )
        self.orders[order.id] = order
        return order

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        return hmac.compare_digest(_sign(self._secret, body), signature)

    def capture(
        self, order_id: str, *, amount_paise: int | None = None
    ) -> SignedWebhook:
        """A signed `payment.captured` webhook. Pass `amount_paise` to fake a mismatch."""
        return self._webhook("payment.captured", "captured", order_id, amount_paise)

    def fail(self, order_id: str) -> SignedWebhook:
        """A signed `payment.failed` webhook."""
        return self._webhook("payment.failed", "failed", order_id, None)

    def _webhook(
        self, event: str, status: str, order_id: str, amount_paise: int | None
    ) -> SignedWebhook:
        order = self.orders[order_id]  # an unknown order is a mistake in the test
        self._payments += 1
        payment = {
            "id": f"pay_fake_{self._payments}",
            "order_id": order.id,
            "amount": order.amount_paise if amount_paise is None else amount_paise,
            "currency": order.currency,
            "status": status,
        }
        body = json.dumps(
            {"event": event, "payload": {"payment": {"entity": payment}}},
            separators=(",", ":"),
        ).encode()
        return SignedWebhook(body=body, signature=_sign(self._secret, body))


class RazorpayPayments:
    """Razorpay over httpx. Not built yet."""

    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder:
        raise NotImplementedError("Razorpay orders arrive with T-8.1.")

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        raise NotImplementedError("Razorpay webhook verification arrives with T-8.2.")
