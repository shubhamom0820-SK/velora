"""`swipes` and `liked_you_reveals` — 03-SCHEMA.md §3."""

from __future__ import annotations

import uuid

from sqlalchemy import Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, pg_enum, uuid_fk
from app.core.enums import SwipeDirection


class Swipe(CreatedAt, Base):
    """One swipe per pair, written once."""

    __tablename__ = "swipes"

    swiper_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    target_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    dir: Mapped[SwipeDirection] = mapped_column(pg_enum(SwipeDirection), nullable=False)

    __table_args__ = (
        # Powers "liked you": who liked or super-liked this person.
        Index(
            "ix_swipes_target_id_likes",
            "target_id",
            "dir",
            postgresql_where=text("dir IN ('like', 'super')"),
        ),
    )


class LikedYouReveal(CreatedAt, Base):
    """A paid reveal of someone who liked the viewer. Written once."""

    __tablename__ = "liked_you_reveals"

    viewer_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    liker_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
