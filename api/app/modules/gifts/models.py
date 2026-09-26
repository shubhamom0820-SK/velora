"""`gifts` and `gift_sends` — 03-SCHEMA.md §5, D-016.

Gifts are sent by men from a woman's profile, before any conversation exists.
They never open a thread or unlock anything (D-003). Prices are data in the
`gifts` table, so no CHECK pins them to particular values — tuning a price must
not need a migration.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, uuid_fk, uuid_pk


class Gift(CreatedAt, Base):
    """The catalogue. Seed data, written by migration (T-1.14)."""

    __tablename__ = "gifts"

    # A slug, e.g. `rose`.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # An emoji or icon key.
    asset: Mapped[str] = mapped_column(Text, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    sort: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    __table_args__ = (CheckConstraint("credits >= 0", name="credits_non_negative"),)


class GiftSend(CreatedAt, Base):
    """A permanent record of one gift, visible to moderation. Written once."""

    __tablename__ = "gift_sends"

    id: Mapped[uuid.UUID] = uuid_pk()
    sender_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    recipient_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    gift_id: Mapped[str] = mapped_column(
        Text, ForeignKey("gifts.id", ondelete="RESTRICT"), nullable=False
    )
    # Copied from the catalogue at send time, so a later price change
    # never rewrites history.
    credits_charged: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # Set if a thread already existed between the two.
    thread_id: Mapped[uuid.UUID | None] = uuid_fk("threads.id", nullable=True)

    __table_args__ = (
        CheckConstraint("sender_id <> recipient_id", name="not_self"),
        CheckConstraint("credits_charged >= 0", name="credits_charged_non_negative"),
        Index(
            "ix_gift_sends_recipient_id_created_at",
            "recipient_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_gift_sends_sender_id_created_at",
            "sender_id",
            text("created_at DESC"),
        ),
        # The per-gift, per-recipient cooldown check (D-016).
        Index(
            "ix_gift_sends_cooldown",
            "sender_id",
            "recipient_id",
            "gift_id",
            text("created_at DESC"),
        ),
    )
