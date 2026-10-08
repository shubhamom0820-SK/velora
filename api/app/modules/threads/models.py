"""`threads` and `thread_clears` — 03-SCHEMA.md §4.

A thread expires `app_config.thread_hours` (an hour since T-7.6, D-097) after
its last move unless both people tie the knot, which makes it a permanent Knot
(D-003); what moves it is D-560. Two CHECKs guard
that promise from both sides, whatever code path writes the row:

- a knotted thread has `knotted_at` and **no** `expires_at` — otherwise the
  expiry cron would kill a conversation both people were told is permanent;
- an active thread **from a match** has `expires_at` — otherwise it would never
  expire. Every way into `active` (open, reopen, untie) sets a fresh
  `thread_hours` expiry — read from app_config, never a literal (checklist A).
  A private message (origin `dm`) never expires (D-231, D-550), so an active
  one carries none.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import ThreadOrigin, ThreadStatus


class Thread(Timestamps, Base):
    """One row per pair, forever."""

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_low: Mapped[uuid.UUID] = uuid_fk("users.id")
    user_high: Mapped[uuid.UUID] = uuid_fk("users.id")
    origin: Mapped[ThreadOrigin] = mapped_column(pg_enum(ThreadOrigin), nullable=False)
    opened_by: Mapped[uuid.UUID] = uuid_fk("users.id")
    status: Mapped[ThreadStatus] = mapped_column(
        pg_enum(ThreadStatus),
        nullable=False,
        server_default=ThreadStatus.ACTIVE.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    low_knot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    high_knot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    knotted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Drives contact masking and call gates.
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint("user_low < user_high", name="pair_ordered"),
        CheckConstraint(
            "status <> 'knotted' OR (knotted_at IS NOT NULL AND expires_at IS NULL)",
            name="knotted_is_permanent",
        ),
        CheckConstraint(
            "status <> 'active' OR expires_at IS NOT NULL OR origin = 'dm'",
            name="active_expires",
        ),
        UniqueConstraint("user_low", "user_high"),
        Index(
            "ix_threads_expiring",
            "expires_at",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_threads_user_low_last_message_at",
            "user_low",
            text("last_message_at DESC"),
        ),
        Index(
            "ix_threads_user_high_last_message_at",
            "user_high",
            text("last_message_at DESC"),
        ),
    )


class ThreadClear(CreatedAt, Base):
    """A one-sided hide (D-006). `cleared_at` is the newest message's
    `created_at` when the clearing ran, or the Thread's opening before any
    (D-610, T-7.8): a point in the messages' own clock, never the time of the
    tap, so a message written after the clearing always shows.

    If a message arrives after `cleared_at`, the thread reappears for that user
    showing only messages newer than it. The other person sees everything.
    Restoring deletes the row (D-611).
    """

    __tablename__ = "thread_clears"

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    thread_id: Mapped[uuid.UUID] = uuid_fk("threads.id", primary_key=True)
    cleared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
