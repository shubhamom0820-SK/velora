"""`sessions` and `banned_identities` — 03-SCHEMA.md §1."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import BanKind


class Session(Timestamps, Base):
    """A refresh-token session. Rotation keeps a family (D-024)."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    # The one foreign key that cascades: sessions mean nothing without the user.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # When the family signed in, copied unchanged at every rotation: the access
    # token's `auth_time` (D-071).
    auth_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index(
            "ix_sessions_user_id_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class BannedIdentity(CreatedAt, Base):
    """A phone hash or device id that may not sign up again, while it stands.

    Never deleted: an admin's unban lifts a `ban` row in place, the three lift
    columns set together, and nothing else ever changes; an `underage` row is
    never lifted (T-9.5, D-922, migration 7c8a628fd3d7's trigger). Sign-in reads
    standing rows only, and one stands per number."""

    __tablename__ = "banned_identities"

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[BanKind] = mapped_column(pg_enum(BanKind), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifted_by: Mapped[uuid.UUID | None] = uuid_fk("users.id", nullable=True)
    lift_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "uq_banned_identities_standing",
            "kind",
            "value",
            unique=True,
            postgresql_where=text("lifted_at IS NULL"),
        ),
        CheckConstraint(
            "(lifted_at IS NULL) = (lifted_by IS NULL) "
            "AND (lifted_at IS NULL) = (lift_reason IS NULL)",
            name="lift_complete",
        ),
    )
