"""Threads — the requests and responses (04-API.md, T-7.1, T-7.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import MessageKind, ThreadOrigin, ThreadStatus
from app.core.pagination import Page
from app.modules.pricing.schemas import ShownPrice

FIRST_MESSAGE_MAX = 500


class OpenThreadRequest(BaseModel):
    """`{match_id}`, a Thread from a match, or `{user_id, first_message}`, a
    private message (D-231): one or the other, never both."""

    model_config = ConfigDict(extra="forbid")

    match_id: UUID | None = None
    user_id: UUID | None = None
    first_message: str | None = Field(
        default=None, min_length=1, max_length=FIRST_MESSAGE_MAX
    )
    # The price shown for opening it (P-56, D-600): compared, never charged.
    shown_price: ShownPrice = 0

    @model_validator(mode="after")
    def _one_or_the_other(self) -> Self:
        from_match = self.match_id is not None
        private = self.user_id is not None or self.first_message is not None
        if from_match == private:
            raise ValueError("send match_id, or user_id with first_message")
        if private and (self.user_id is None or self.first_message is None):
            raise ValueError("a private message needs user_id and first_message")
        if self.first_message is not None and not self.first_message.strip():
            raise ValueError("first_message can't be blank")
        return self


class Thread(BaseModel):
    """A Thread as one of its two people sees it.

    `expires_at` is shown to a man only: her side has no countdown (D-097,
    08-DESIGN §8, D-554), and is null for her, as it is once knotted and for a
    private message, which never expires (D-231)."""

    id: UUID
    origin: ThreadOrigin
    status: ThreadStatus
    other_user_id: UUID
    expires_at: datetime | None
    knotted_at: datetime | None
    # Whether you have tapped "Tie the knot".
    i_tied: bool
    last_message_at: datetime | None
    created_at: datetime


# --- The list (T-7.2) ---------------------------------------------------------------

Q_MAX = 50


class CardLite(BaseModel):
    """The other person, as a row in the chats list. A deleted account is
    `deleted`, with no name, username or photo, from the moment they delete
    (D-051, D-500); the Thread and its messages stay."""

    id: UUID
    first_name: str | None
    username: str | None
    main_photo_url: str | None
    shows_badge: bool
    is_online: bool
    deleted: bool


class LastMessage(BaseModel):
    """A row's preview. `text` is a text message's first 100 characters, as
    shown (masked); a voice note has none, and the web names it."""

    kind: MessageKind
    text: str | None
    mine: bool
    at: datetime


class ThreadRow(BaseModel):
    """One Thread in the chats list. `expires_at` is a man's alone (D-554)."""

    id: UUID
    origin: ThreadOrigin
    status: ThreadStatus
    expires_at: datetime | None
    knotted_at: datetime | None
    i_tied: bool
    unread: int
    last_message: LastMessage | None
    last_message_at: datetime | None
    other: CardLite


class ThreadRowPage(Page[ThreadRow]):
    """`Page<ThreadRow>`: newest first, by the last message or, before any,
    the opening, then id."""


# --- Clearing (T-7.8) ---------------------------------------------------------------

CLEAR_MAX = 100


class ClearThreadsRequest(BaseModel):
    """`{thread_ids}`, the chats chosen in select mode, or `{expired: true}`,
    every expired Thread in my list ("Clear expired"): one or the other."""

    model_config = ConfigDict(extra="forbid")

    thread_ids: list[UUID] | None = Field(
        default=None, min_length=1, max_length=CLEAR_MAX
    )
    expired: bool | None = None

    @model_validator(mode="after")
    def _one_or_the_other(self) -> Self:
        if (self.thread_ids is None) == (self.expired is None):
            raise ValueError("send thread_ids, or expired: true")
        if self.expired is False:
            raise ValueError("expired can only be true")
        return self


class Cleared(BaseModel):
    """How many of the request's Threads are now cleared for you: of the ids,
    those that are yours; of `expired`, those that were in your list."""

    cleared: int
