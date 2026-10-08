"""`data_exports` — 03-SCHEMA.md §1 (T-9.6, D-502).

One row per export a user asks for: the worker writes the file, the API signs a
link to it until `expires_at`, 24 hours after it was ready, and the file is
deleted then (`expired`). The file holds the user's phone number, so it lives
in the private bucket and never longer than its link.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, uuid_fk, uuid_pk

EXPORT_STATUSES = ("pending", "ready", "failed", "expired")


class DataExport(Timestamps, Base):
    __tablename__ = "data_exports"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    # The private bucket's key while the file exists: ready, or expired with
    # its deletion not yet read back as done.
    file_key: Mapped[str | None] = mapped_column(Text)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'expired')", name="status_known"
        ),
        CheckConstraint(
            "status <> 'ready' OR (file_key IS NOT NULL AND ready_at IS NOT NULL "
            "AND expires_at IS NOT NULL)",
            name="ready_has_a_file",
        ),
        Index("ix_data_exports_user_id_created_at", "user_id", text("created_at DESC")),
    )
