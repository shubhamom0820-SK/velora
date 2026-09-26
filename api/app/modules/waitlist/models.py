"""`waitlist` — 03-SCHEMA.md §8.

No email-format CHECK: T-2.3 validates in the API, and a regex in the database
rejects valid addresses while catching nothing real. citext makes the unique
constraint case-insensitive.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, uuid_pk


class WaitlistEntry(CreatedAt, Base):
    """Written once."""

    __tablename__ = "waitlist"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    city: Mapped[str | None] = mapped_column(Text)
