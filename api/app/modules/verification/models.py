"""`verifications` — 03-SCHEMA.md §2."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, pg_enum, uuid_pk
from app.core.enums import ReviewStatus


class Verification(Timestamps, Base):
    __tablename__ = "verifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selfie_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="RESTRICT")
    )
    challenge: Mapped[str] = mapped_column(Text, nullable=False)
    liveness_ok: Mapped[bool | None] = mapped_column(Boolean)
    similarity: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus),
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
    )

    __table_args__ = (
        Index(
            "ix_verifications_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
    )
