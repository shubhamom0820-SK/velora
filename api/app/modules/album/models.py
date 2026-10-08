"""`album_requests` and `album_copies` — 03-SCHEMA.md §5."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import AlbumRequestStatus


class AlbumRequest(Timestamps, Base):
    """A request to see someone's private album. What it cost is spent: a
    decline or a revoke returns nothing (D-230)."""

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


class AlbumCopy(CreatedAt, Base):
    """One private photo watermarked for one granted request's viewer (T-8.4,
    D-730), in the private bucket at `file_key`. The row is the record that the
    file exists: written only once the file is, and deleted only once the file
    is gone, so a revoke, the erasure (D-503) and an under-18 refusal (D-078)
    find every copy by its `*_key` column."""

    __tablename__ = "album_copies"

    id: Mapped[uuid.UUID] = uuid_pk()
    request_id: Mapped[uuid.UUID] = uuid_fk("album_requests.id")
    photo_id: Mapped[uuid.UUID] = uuid_fk("photos.id")
    # The request's two people, so either one's erasure finds the copy.
    owner_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    viewer_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    file_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    __table_args__ = (
        UniqueConstraint("request_id", "photo_id"),
        Index("ix_album_copies_owner_id", "owner_id"),
        Index("ix_album_copies_viewer_id", "viewer_id"),
    )
