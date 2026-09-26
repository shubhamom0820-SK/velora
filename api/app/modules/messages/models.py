"""`messages` and `message_unlocks` — 03-SCHEMA.md §4.

`body_raw` is the original text, kept for moderation only. It must never be
returned by a user-facing endpoint (06-TESTING.md critical test 11), and never
logged (CLAUDE.md rule 15). `body` is what users see, masked where needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAt, Timestamps, pg_enum, uuid_fk, uuid_pk
from app.core.enums import MessageKind


class Message(Timestamps, Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = uuid_fk("threads.id")
    sender_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    kind: Mapped[MessageKind] = mapped_column(pg_enum(MessageKind), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    body_raw: Mapped[str | None] = mapped_column(Text)
    media_key: Mapped[str | None] = mapped_column(Text)
    duration_s: Mapped[int | None] = mapped_column(SmallInteger)
    # Client-generated, so a retried send is stored once.
    client_msg_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    masked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("char_length(body) <= 2000", name="body_length"),
        UniqueConstraint("sender_id", "client_msg_id"),
        Index(
            "ix_messages_thread_id_created_at",
            "thread_id",
            text("created_at DESC"),
        ),
    )


class MessageUnlock(CreatedAt, Base):
    """A man paying to hear a voice note. Written once."""

    __tablename__ = "message_unlocks"

    user_id: Mapped[uuid.UUID] = uuid_fk("users.id", primary_key=True)
    message_id: Mapped[uuid.UUID] = uuid_fk("messages.id", primary_key=True)
