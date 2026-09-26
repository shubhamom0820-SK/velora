"""`kudos` — 03-SCHEMA.md §5, D-007.

A fixed positive note, sent privately after a conversation; the recipient alone
decides whether it shows (`profiles.show_kudos`). Allowed only once the thread
has `app_config.kudos_min_messages` messages — enforced in the service.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, pg_enum, uuid_fk, uuid_pk
from app.core.enums import Kudos as KudosKind


class Kudos(CreatedAt, Base):
    """Written once."""

    __tablename__ = "kudos"

    id: Mapped[uuid.UUID] = uuid_pk()
    from_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    to_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    kind: Mapped[KudosKind] = mapped_column(pg_enum(KudosKind), nullable=False)
    thread_id: Mapped[uuid.UUID] = uuid_fk("threads.id")

    __table_args__ = (
        # Self-kudos would let someone manufacture social proof on their profile.
        CheckConstraint("from_id <> to_id", name="not_self"),
        UniqueConstraint("from_id", "to_id"),
    )
