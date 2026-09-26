"""`matches` — 03-SCHEMA.md §3."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.core.db import Base, Timestamps, uuid_fk, uuid_pk


class Match(Timestamps, Base):
    """A mutual like. The pair is stored ordered, so each pair has one row."""

    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_low: Mapped[uuid.UUID] = uuid_fk("users.id")
    user_high: Mapped[uuid.UUID] = uuid_fk("users.id")
    # Set when a thread is opened from the match.
    thread_id: Mapped[uuid.UUID | None] = uuid_fk("threads.id", nullable=True)

    __table_args__ = (
        CheckConstraint("user_low < user_high", name="pair_ordered"),
        UniqueConstraint("user_low", "user_high"),
    )
