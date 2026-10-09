"""`push_subscriptions`, `notification_prefs`, `notifications`, `push_outbox` —
03-SCHEMA.md §7."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    Text,
    false,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, uuid_fk, uuid_pk


class PushSubscription(CreatedAt, Base):
    """A browser's Web Push subscription. `last_ok_at` is its own timestamp.

    `p256dh` and `auth` are the subscription's encryption keys: secrets. Never
    log them (CLAUDE.md rule 15) and never return them from an endpoint.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPrefs(Timestamps, Base):
    """One row per user, created at signup (T-3.3)."""

    __tablename__ = "notification_prefs"

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    match: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    message: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    # The column is `likes`: `like` is a reserved word in Postgres, and unquoted
    # `create table t (like boolean)` even parses as a different clause. The
    # attribute — and so the API's `Prefs.like` field — keeps the name `like`.
    like: Mapped[bool] = mapped_column(
        "likes", Boolean, nullable=False, server_default=true()
    )
    knot: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    balance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    # T-9.4 (D-851): gifts (P-550), and album requests and answers (P-631).
    gift: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    album: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    # Generic push text ("You have a new message") instead of names: off by default.
    generic_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )


class Notification(CreatedAt, Base):
    """The in-app list. `read_at` is its own timestamp."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_notifications_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
    )


class PushOutbox(CreatedAt, Base):
    """A push waiting to be sent (T-9.4, D-850), written in the transaction
    that makes it true. The worker claims it (`claimed_at`), sends it with no
    lock held, and deletes it once sent, skipped or given up on."""

    __tablename__ = "push_outbox"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        Index("ix_push_outbox_created_at", "created_at"),
        Index("ix_push_outbox_user_id", "user_id"),
    )
