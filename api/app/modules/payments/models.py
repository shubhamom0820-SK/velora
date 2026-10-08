"""`credit_packs`, `payments`, `refund_requests` — 03-SCHEMA.md §6.

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
    """`status` is free text on purpose: T-8.3 owns the refund workflow and
    defines its values; guessing an enum now would mean a migration later."""

    __tablename__ = "refund_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    payment_id: Mapped[uuid.UUID] = uuid_fk("payments.id")
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
