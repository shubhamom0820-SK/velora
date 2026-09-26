"""`profile_views` — 03-SCHEMA.md §3."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, uuid_fk


class ProfileView(CreatedAt, Base):
    """One row per viewer and profile, bumped on every view.

    `last_viewed_at` is the update timestamp, so there is no `updated_at`.
    Not written when the viewer is incognito (backlog B-7).
    """

    __tablename__ = "profile_views"

    viewer_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    viewed_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    last_viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )

    __table_args__ = (
        Index(
            "ix_profile_views_viewed_id_last_viewed_at",
            "viewed_id",
            text("last_viewed_at DESC"),
        ),
    )
