"""`album_requests` — 03-SCHEMA.md §5."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import AlbumRequestStatus


class AlbumRequest(Timestamps, Base):
    """A request to see someone's private album. Refunded if declined."""

    __tablename__ = "album_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    requester_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    owner_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    status: Mapped[AlbumRequestStatus] = mapped_column(
        pg_enum(AlbumRequestStatus),
        nullable=False,
        server_default=AlbumRequestStatus.PENDING.value,
    )
    credits_charged: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("requester_id <> owner_id", name="not_self"),
        # A charge is never negative; a refund is its own ledger entry.
        CheckConstraint("credits_charged >= 0", name="credits_charged_non_negative"),
        # One live request per pair; a declined or revoked one frees it.
        Index(
            "uq_album_requests_live_pair",
            "requester_id",
            "owner_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'granted')"),
        ),
    )
