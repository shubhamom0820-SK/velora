"""`profiles`, `areas`, `interests`, `profile_interests` — 03-SCHEMA.md §2.

Everything on a profile except its key is nullable: T-3.3 creates the row at
signup, before onboarding has filled anything in. Length and format rules are
CHECKs, which pass on NULL.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_pk
from app.core.enums import Intent, Seeking


def _point() -> Geography:
    # spatial_index=False: the GIST index is declared explicitly below, so it
    # follows our naming convention instead of geoalchemy2's `idx_…`.
    return Geography(geometry_type="POINT", srid=4326, spatial_index=False)


class Profile(Timestamps, Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    first_name: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    about: Mapped[str | None] = mapped_column(Text)
    hometown: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas.id", ondelete="RESTRICT")
    )
    location: Mapped[Any | None] = mapped_column(_point())
    location_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    seeking: Mapped[Seeking | None] = mapped_column(pg_enum(Seeking))
    intent: Mapped[Intent | None] = mapped_column(pg_enum(Intent))
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    hide_age: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    hide_distance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    show_kudos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    show_gifts: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
    completeness: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "username::text ~ '^[a-z0-9._]{4,20}$'", name="username_format"
        ),
        CheckConstraint(
            "char_length(first_name) BETWEEN 1 AND 30", name="first_name_length"
        ),
        CheckConstraint("char_length(about) BETWEEN 40 AND 300", name="about_length"),
        CheckConstraint("char_length(hometown) <= 40", name="hometown_length"),
        CheckConstraint("char_length(city) <= 40", name="city_length"),
        CheckConstraint("completeness BETWEEN 0 AND 100", name="completeness_range"),
        Index("ix_profiles_location", "location", postgresql_using="gist"),
        Index(
            "ix_profiles_username_trgm",
            "username",
            postgresql_using="gin",
            postgresql_ops={"username": "gin_trgm_ops"},
        ),
        Index(
            "ix_profiles_first_name_trgm",
            "first_name",
            postgresql_using="gin",
            postgresql_ops={"first_name": "gin_trgm_ops"},
        ),
        Index("ix_profiles_intent", "intent"),
        Index("ix_profiles_is_hidden", "is_hidden"),
    )


class Area(CreatedAt, Base):
    """Seed data: neighbourhoods for the manual location fallback (D-034)."""

    __tablename__ = "areas"

    id: Mapped[uuid.UUID] = uuid_pk()
    city: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    centroid: Mapped[Any | None] = mapped_column(_point())

    __table_args__ = (UniqueConstraint("city", "name"),)


class Interest(CreatedAt, Base):
    """Seed data: the 24 interests (T-1.14). A fixed smallint id, not a uuid."""

    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    slug: Mapped[str | None] = mapped_column(Text, unique=True)
    label: Mapped[str | None] = mapped_column(Text)


class ProfileInterest(CreatedAt, Base):
    """Exactly 5 per user — enforced in the service, not here."""

    __tablename__ = "profile_interests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    interest_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("interests.id", ondelete="RESTRICT"),
        primary_key=True,
    )
