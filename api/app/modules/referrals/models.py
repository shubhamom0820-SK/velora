"""`referrals` — 03-SCHEMA.md §6.

Both sides are rewarded (credits from app_config) only after the referee's first
paid purchase or selfie verification, whichever comes first (T-8.6).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, uuid_fk


class Referral(CreatedAt, Base):
    """One referrer per referee. `rewarded_at` is its own update timestamp."""

    __tablename__ = "referrals"

    referee_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    referrer_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # A self-referral would farm credits on both sides of one account.
        CheckConstraint("referee_id <> referrer_id", name="not_self"),
    )
