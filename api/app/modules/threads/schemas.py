"""Threads — the requests and responses (04-API.md, T-7.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ThreadOrigin, ThreadStatus

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
