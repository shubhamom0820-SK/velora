"""`GET /v1/packs`, `POST /v1/payments/orders`, `GET /v1/admin/turnover`
(04-API.md, T-8.1), `POST /v1/payments/webhook` and `GET /v1/payments/{id}`
(T-8.2).

**No GST, anywhere a user is shown a payment, while Velora is unregistered**
(D-450, D-482): not a field, not a word. Showing GST without a GSTIN is against
the law. P-350 adds the line when Velora registers; a test reads each response
for the letters "gst" in any case.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import PaymentStatus


class Pack(BaseModel):
    """A pack in this man's store. `bonus_credits` is what he would get on top
    if he bought it now: the first-purchase bonus, or 0 (D-231)."""

    id: str
    credits: int
    price_paise: int
    bonus_credits: int


class OrderRequest(BaseModel):
    """Only the pack: the amount and the Velas come from its row, never from
    the browser (rule 6), so a body naming either is refused."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str


class Order(BaseModel):
    """What Checkout opens with: our payment, the gateway's order, its public
    key, and the amount, the pack's price (inclusive, D-099)."""

    payment_id: UUID
    order_id: str
    key_id: str
    amount_paise: int


class PaymentStatusView(BaseModel):
    """What the browser polls after Checkout: the status, and the Velas the
    payment grants or granted. `bonus_credits` is 0 once a capture finds an
    earlier purchase of his (P-380), so the poll tells the truth."""

    status: PaymentStatus
    credits: int
    bonus_credits: int


class WebhookReceived(BaseModel):
    """`{}`: Razorpay reads the status alone."""


class Turnover(BaseModel):
    """The financial year's aggregate turnover, for the admin (D-483): the sum
    of paid payments, beside the alert and the threshold (P-350)."""

    financial_year: str
    starts_at: datetime
    ends_at: datetime
    turnover_paise: int
    paid_payments: int
    alert_at_paise: int
    threshold_paise: int
