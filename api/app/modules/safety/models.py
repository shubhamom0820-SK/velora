"""`blocks`, `reports`, `fraud_scores`, `fraud_events` — 03-SCHEMA.md §5.

Reports are never hard-deleted (CLAUDE.md rule 12): moderation needs them.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import FraudBand, ReportReason, ReportStatus


class Block(CreatedAt, Base):
    """Blocks are total (06-TESTING.md critical test 9), and hold against the
    blocked person's number as well as the account (D-861). Unblocking sets
    `unblocked_at` and keeps the row (D-860): one standing block per pair, as
    many lifted ones as there have been. Only the erasure (D-503) and an
    under-18 refusal (D-072) delete one."""

    __tablename__ = "blocks"

    id: Mapped[uuid.UUID] = uuid_pk()
    blocker_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    blocked_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    unblocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("blocker_id <> blocked_id", name="not_self"),
        Index(
            "uq_blocks_active",
            "blocker_id",
            "blocked_id",
            unique=True,
            postgresql_where=text("unblocked_at IS NULL"),
        ),
        Index("ix_blocks_blocked_id", "blocked_id"),
    )


class Report(Timestamps, Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    reporter_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    reported_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    reason: Mapped[ReportReason] = mapped_column(pg_enum(ReportReason), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    # Context: the conversation the report came from, if any.
    thread_id: Mapped[uuid.UUID | None] = uuid_fk("threads.id", nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        pg_enum(ReportStatus),
        nullable=False,
        server_default=ReportStatus.OPEN.value,
    )
    action: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # A self-report could be used to probe the auto-freeze rule (D-031).
        CheckConstraint("reporter_id <> reported_id", name="not_self"),
        CheckConstraint("char_length(details) <= 500", name="details_length"),
        CheckConstraint(
            "action IN ('freeze', 'ban', 'warn', 'none')", name="action_values"
        ),
        Index("ix_reports_status_created_at", "status", "created_at"),
        Index(
            "ix_reports_reported_id_created_at",
            "reported_id",
            text("created_at DESC"),
        ),
        # A person's own reports, newest first (`GET /reports`, T-9.8).
        Index(
            "ix_reports_reporter_id_created_at",
            "reporter_id",
            text("created_at DESC"),
        ),
    )


class FraudScore(Timestamps, Base):
    """Recomputed by a worker (D-031). Bands are policy, so they are not tied to
    the score by a CHECK — tuning a threshold must not need a migration."""

    __tablename__ = "fraud_scores"

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    score: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    band: Mapped[FraudBand] = mapped_column(
        pg_enum(FraudBand),
        nullable=False,
        server_default=FraudBand.NORMAL.value,
    )
    signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),)


class FraudEvent(CreatedAt, Base):
    """One behavioural signal. Written once."""

    __tablename__ = "fraud_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    signal: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        Index(
            "ix_fraud_events_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
    )
