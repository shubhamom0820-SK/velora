"""`welcome_grants` — 03-SCHEMA.md §1 (T-8.11, D-470, P-371).

One row per phone number that received welcome Velas, keyed by the number's
hash (`users.phone_hash`, D-061), so a number gets them once, ever: a later
account on it, once T-9.6 has erased the first, finds it claimed. Append-only:
`refuse_change()` refuses UPDATE, DELETE and TRUNCATE, and the erasure keeps it
(D-503).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, uuid_fk


class WelcomeGrant(CreatedAt, Base):
    __tablename__ = "welcome_grants"

    phone_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    # The account that received it.
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")

    __table_args__ = (UniqueConstraint("user_id"),)
