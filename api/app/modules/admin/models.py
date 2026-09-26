"""`audit_log`, `app_config` — 03-SCHEMA.md §8."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, uuid_fk, uuid_pk


class AuditLogEntry(CreatedAt, Base):
    """Every admin action (02-ARCHITECTURE §12), including a moderator reading
    someone's messages with body_raw (T-9.5).

    Append-only in the database: UPDATE, DELETE and TRUNCATE are refused
    (migration T-1.13, reusing T-1.12's refuse_change) — otherwise the one person
    with a reason to erase the trace is exactly the person who can.

    `actor_id` is never NULL: NULL could not tell "the system did it" from "a bug
    forgot to set it". Automated actions get a dedicated system user (T-9.2).
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # Polymorphic, like ledger_entries.ref_*, so target_id cannot carry an FK.
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(
            "(target_type IS NULL) = (target_id IS NULL)", name="target_complete"
        ),
    )


class AppConfig(Timestamps, Base):
    """Tunable settings, read everywhere through a cached accessor (60 s) and
    written from the admin panel. Seeds arrive with T-1.14."""

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
