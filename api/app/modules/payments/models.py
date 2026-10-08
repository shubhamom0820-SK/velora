"""`credit_packs`, `payments`, `refund_requests`, `payment_reversals` — 03-SCHEMA.md §6.

Credits are granted only by the verified webhook, idempotent on
`provider_payment_id` (D-026). Money is integer paise (D-029). Payments are never
hard-deleted (CLAUDE.md rule 12): the database refuses DELETE and TRUNCATE
(migration T-1.12); status updates are allowed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import PaymentStatus


class CreditPack(CreatedAt, Base):
    """The catalogue (D-005). A price change is a row update; `payments` copies
    amount and credits at order time, so no history is lost."""

    __tablename__ = "credit_packs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_first_pct: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("20")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    sort: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    # For the beta price test (T-10.4). Variants are policy: no CHECK.
    variant: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'A'")
    )

    __table_args__ = (
        # Invariants, not policy: the values themselves stay free to tune.
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint("price_paise > 0", name="price_positive"),
        CheckConstraint(
            "bonus_first_pct BETWEEN 0 AND 100", name="bonus_first_pct_range"
        ),
    )


class Payment(Timestamps, Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    pack_id: Mapped[str] = mapped_column(
        Text, ForeignKey("credit_packs.id", ondelete="RESTRICT"), nullable=False
    )
    # Copied from the pack at order time.
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_credits: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # The government's part of `amount_paise`, which is GST-inclusive (D-099,
    # D-450): 0 while Velora is unregistered, as it is until P-350, which splits
    # each new payment's amount and never moves it.
    gst_paise: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # The client's `Idempotency-Key` for the order: one order per key per user,
    # however many times it is sent, at once or later (D-481).
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'razorpay'")
    )
    provider_order_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # The idempotency anchor: a captured payment is credited once (D-026).
    provider_payment_id: Mapped[str | None] = mapped_column(Text, unique=True)
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus),
        nullable=False,
        server_default=PaymentStatus.CREATED.value,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The last verified webhook payload.
    raw_webhook: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="amount_positive"),
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint("bonus_credits >= 0", name="bonus_non_negative"),
        # Part of the amount, never more: the price doesn't move (D-450).
        CheckConstraint(
            "gst_paise >= 0 AND gst_paise < amount_paise", name="gst_within_amount"
        ),
        UniqueConstraint("user_id", "idempotency_key"),
        # Once money has moved, the anchor must exist — a paid row without it
        # would silently break webhook idempotency and credit a payment twice.
        CheckConstraint(
            "status NOT IN ('paid', 'refunded') "
            "OR (provider_payment_id IS NOT NULL AND paid_at IS NOT NULL)",
            name="paid_has_anchor",
        ),
    )


class RefundRequest(Timestamps, Base):
    """A claim that a payment broke (T-8.3, D-580): `missing_velas` or
    `duplicate_charge`, never a change of mind (D-050, D-230). An admin resolves
    it from what the gateway says: `granted`, `refunded` or `rejected`
    (`payments/claims.py`). A refund's record is here, with the gateway's ids:
    the payment refunded has no row of its own, and the credited one is never
    touched (D-580)."""

    __tablename__ = "refund_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    payment_id: Mapped[uuid.UUID] = uuid_fk("payments.id")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    # The admin's, required on a rejection: never the user's words.
    note: Mapped[str | None] = mapped_column(Text)
    # A refund's: the gateway's payment returned, and its refund.
    provider_payment_id: Mapped[str | None] = mapped_column(Text)
    provider_refund_id: Mapped[str | None] = mapped_column(Text, unique=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "reason IN ('missing_velas', 'duplicate_charge')", name="reason_known"
        ),
        CheckConstraint(
            "status IN ('open', 'granted', 'refunded', 'rejected')",
            name="status_known",
        ),
        CheckConstraint(
            "(status = 'open') = (resolved_at IS NULL)", name="resolved_when_closed"
        ),
        CheckConstraint(
            "status <> 'refunded' "
            "OR (provider_payment_id IS NOT NULL AND provider_refund_id IS NOT NULL)",
            name="refund_names_its_ids",
        ),
        CheckConstraint(
            "status <> 'rejected' OR note IS NOT NULL", name="rejection_has_note"
        ),
        # One open claim per payment.
        Index(
            "uq_refund_requests_open_per_payment",
            "payment_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )


class PaymentReversal(CreatedAt, Base):
    """Every refund and dispute the webhook handled, once, by its own Razorpay
    id, with what its reversal took and what it couldn't (P-420, D-581). The
    repeat check reads it: a reversal that took 0 wrote no ledger entry, so
    without this a redelivery would take from Velas bought since.

    Append-only in the database (migration d4f1d16b2191)."""

    __tablename__ = "payment_reversals"

    id: Mapped[uuid.UUID] = uuid_pk()
    payment_id: Mapped[uuid.UUID] = uuid_fk("payments.id")
    # `rfnd_…` or `disp_…`.
    provider_ref: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    taken: Mapped[int] = mapped_column(Integer, nullable=False)
    shortfall: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('refund', 'dispute')", name="kind_known"),
        CheckConstraint("taken >= 0", name="taken_non_negative"),
        CheckConstraint("shortfall >= 0", name="shortfall_non_negative"),
    )
