"""Payments: Razorpay orders and webhooks (D-026, T-8.1, T-8.2).

Credits are granted only by a verified webhook. The fake signs its webhooks
with HMAC-SHA256 of the raw body, as Razorpay does, so the webhook route runs
the same verification code in tests as in production.

An order the gateway can't create raises `PaymentsUnavailable`, which the API
answers with `PROVIDER_UNAVAILABLE` (503); its message names what failed, never
a key.

**A webhook's signature** (T-8.2, Razorpay's webhook docs, read 8 October 2026):
`X-Razorpay-Signature` is the hex HMAC-SHA256 of the raw request body, keyed by
the webhook secret, compared in constant time. Without the secret every
signature is refused, with an error naming the setting (P-382).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Final, Literal, Protocol

import httpx
import structlog

log = structlog.get_logger(__name__)


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


class PaymentsUnavailable(Exception):
    """The gateway didn't create the order: down, refusing, or not configured.
    The message says which, and never carries a key."""


class PaymentsProvider(Protocol):
    @property
    def key_id(self) -> str:
        """The public key Checkout opens with: not a secret (D-085's sense)."""
        ...

    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder:
        """Create the gateway's order; `receipt` is our own reference for it.
        Raises `PaymentsUnavailable` if it can't."""
        ...

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        """True only if `signature` is the gateway's signature of the raw `body`."""
        ...

    async def aclose(self) -> None:
        """Close any connection it opened. Safe to call more than once."""
        ...


def _sign(secret: bytes, body: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _signed_by(secret: bytes, body: bytes, signature: str) -> bool:
    """In constant time, and as bytes: a header of any characters is a refusal,
    never a `TypeError`."""
    return hmac.compare_digest(
        _sign(secret, body).encode(), signature.encode("utf-8", "surrogateescape")
    )


Outcome = Literal["captured", "failed"]


class FakePayments:
    """Orders in memory, and webhooks signed with a fixed local secret.

    `capture(order_id)` and `fail(order_id)` build the webhook the gateway
    would send for an order it made, for a test to deliver. `webhook()` builds
    one from an order's id and amount alone: T-8.1's local-only simulator reads
    those from the `payments` row, so it works after the API restarts and the
    orders in memory are gone.
    """

    _secret = b"fake-payments-local-only"
    key_id = "rzp_fake_local_only"

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
        return _signed_by(self._secret, body, signature)

    def capture(
        self, order_id: str, *, amount_paise: int | None = None
    ) -> SignedWebhook:
        """A signed `payment.captured` webhook. Pass `amount_paise` to fake a mismatch."""
        return self._webhook("payment.captured", "captured", order_id, amount_paise)

    def fail(self, order_id: str) -> SignedWebhook:
        """A signed `payment.failed` webhook."""
        return self._webhook("payment.failed", "failed", order_id, None)

    def sign(self, event: dict[str, object] | bytes) -> SignedWebhook:
        """Any event, or any body, signed as the gateway would sign it: for a
        test that needs a refund, a dispute, or a payload of its own (T-8.2)."""
        body = (
            event
            if isinstance(event, bytes)
            else json.dumps(event, separators=(",", ":")).encode()
        )
        return SignedWebhook(body=body, signature=_sign(self._secret, body))

    def _webhook(
        self, event: str, status: str, order_id: str, amount_paise: int | None
    ) -> SignedWebhook:
        order = self.orders[order_id]  # an unknown order is a mistake in the test
        return self._signed(
            event,
            status,
            order.id,
            order.amount_paise if amount_paise is None else amount_paise,
        )

    def webhook(
        self, outcome: Outcome, *, order_id: str, amount_paise: int
    ) -> SignedWebhook:
        """The signed webhook for an order known only by its id and amount."""
        event = "payment.captured" if outcome == "captured" else "payment.failed"
        return self._signed(event, outcome, order_id, amount_paise)

    def _signed(
        self, event: str, status: str, order_id: str, amount_paise: int
    ) -> SignedWebhook:
        self._payments += 1
        payment = {
            "id": f"pay_fake_{self._payments}",
            "order_id": order_id,
            "amount": amount_paise,
            "currency": "INR",
            "status": status,
        }
        body = json.dumps(
            {"event": event, "payload": {"payment": {"entity": payment}}},
            separators=(",", ":"),
        ).encode()
        return SignedWebhook(body=body, signature=_sign(self._secret, body))

    async def aclose(self) -> None:
        return None


RAZORPAY_API: Final = "https://api.razorpay.com/v1"
# Long enough for a slow gateway, short enough that a man at checkout isn't
# left waiting on a request that won't come back.
ORDER_TIMEOUT_S: Final = 10.0


class RazorpayPayments:
    """Razorpay over httpx: `POST /v1/orders`, basic auth with the key id and
    secret, the amount in paise, INR, and our payment's id as the receipt
    (Razorpay's Orders API, read 8 October 2026: at most 40 ASCII characters,
    unique; a UUID is 36).

    Built to the documentation and tested against a mock transport: no call has
    reached Razorpay yet, since there is no account (P-0.8). Without keys it
    refuses each order, `PaymentsUnavailable`, rather than refusing to start:
    staging and production run `PAYMENTS_PROVIDER=razorpay`, and without the
    account they can have no keys, so a startup check waits for it (P-382).

    The client opens on first use, so the worker, which builds every provider
    and never orders, opens none. The keys go in the Authorization header, never
    the URL, which httpx logs.
    """

    def __init__(
        self,
        key_id: str = "",
        key_secret: str = "",
        *,
        webhook_secret: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    @property
    def key_id(self) -> str:
        return self._key_id

    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder:
        if not (self._key_id and self._key_secret):
            raise PaymentsUnavailable(
                "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET aren't set (P-0.8, P-382)"
            )
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=RAZORPAY_API,
                timeout=ORDER_TIMEOUT_S,
                transport=self._transport,
            )
        try:
            response = await self._client.post(
                "/orders",
                auth=(self._key_id, self._key_secret),
                json={"amount": amount_paise, "currency": "INR", "receipt": receipt},
            )
        except httpx.HTTPError as error:
            raise PaymentsUnavailable(
                f"Razorpay didn't answer: {type(error).__name__}"
            ) from None
        if not response.is_success:
            raise PaymentsUnavailable(
                f"Razorpay refused the order: HTTP {response.status_code}"
            )
        return _order_from(response, amount_paise)

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        if not self._webhook_secret:
            log.error(
                "payments.webhook_secret_missing",
                note="RAZORPAY_WEBHOOK_SECRET isn't set: every webhook is refused (P-382).",
            )
            return False
        return _signed_by(self._webhook_secret.encode(), body, signature)

    async def aclose(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()


def _order_from(response: httpx.Response, amount_paise: int) -> ProviderOrder:
    """The order Razorpay says it made, if it is the one we asked for: an id,
    our amount, in rupees. Anything else is refused, never trusted."""
    try:
        body = response.json()
        order_id, amount, currency = body["id"], body["amount"], body["currency"]
    except (ValueError, KeyError, TypeError):
        raise PaymentsUnavailable("Razorpay's answer wasn't an order") from None
    if not (isinstance(order_id, str) and order_id.startswith("order_")):
        raise PaymentsUnavailable("Razorpay's answer had no order id")
    if amount != amount_paise or currency != "INR":
        raise PaymentsUnavailable("Razorpay's order isn't for the amount asked")
    return ProviderOrder(id=order_id, amount_paise=amount_paise)
