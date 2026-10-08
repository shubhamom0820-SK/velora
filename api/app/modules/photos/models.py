"""`photos` — 03-SCHEMA.md §2."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, pg_enum, uuid_pk
from app.core.enums import PhotoKind, ReviewStatus


class Photo(Timestamps, Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[PhotoKind] = mapped_column(pg_enum(PhotoKind), nullable=False)
    # Public photos must hold a slot, 0–5, where 0 is the main one (P-13: NULL
    # would pass a plain BETWEEN check). No range is set for other kinds.
    position: Mapped[int | None] = mapped_column(SmallInteger)
    raw_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str | None] = mapped_column(Text)
    # An approved private photo's scored copy (P-79, D-700): what anyone but
    # its owner is ever shown, never the upload a second PUT could replace.
    scored_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus),
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
    )
    reject_reason: Mapped[str | None] = mapped_column(Text)
    moderation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "kind <> 'public' OR (position IS NOT NULL AND position BETWEEN 0 AND 5)",
            name="public_position_range",
        ),
        Index("ix_photos_user_id_kind_position", "user_id", "kind", "position"),
        Index(
            "ix_photos_pending",
            "status",
            postgresql_where=text("status = 'pending'"),
        ),
        # One live public photo per slot; a rejected photo frees its slot.
        Index(
            "uq_photos_public_position",
            "user_id",
            "position",
            unique=True,
            postgresql_where=text("kind = 'public' AND status <> 'rejected'"),
        ),
    )
