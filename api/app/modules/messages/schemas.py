"""Messages — the requests and responses (04-API.md, T-7.1, T-7.3, T-7.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import MessageKind
from app.core.pagination import Page
from app.modules.pricing.schemas import ShownPrice

BODY_MAX = 2000


class Message(BaseModel):
    """One message, as one of the Thread's two people sees it.

    `body` is the text shown, masked where it had to be (`masked`, D-030);
    never the original, which only moderation reads. A voice note never
    carries its file here: `locked` says whether a man still has to unlock it,
    and the file is fetched on its own (T-7.9). `client_msg_id` only on your
    own messages, for the web to match its sends.
    """

    id: UUID
    thread_id: UUID
    kind: MessageKind
    body: str | None
    masked: bool
    duration_s: int | None
    mine: bool
    # The sender deleted their account (D-051, D-500): shown as "Deleted
    # account", and kept.
    from_deleted_account: bool
    locked: bool
    read_at: datetime | None
    created_at: datetime
    client_msg_id: UUID | None


class MessagePage(Page[Message]):
    """`Page<Message>`: newest first by `(created_at, id)`."""


class SendMessageRequest(BaseModel):
    """`{client_msg_id, kind, body?, media_key?, duration_s?}`. Text: a body of
    1 to 2,000 characters, not all spaces, and nothing else. A voice note's
    fields are T-7.9's; until then one is refused by the service."""

    model_config = ConfigDict(extra="forbid")

    client_msg_id: UUID
    kind: MessageKind
    body: str | None = Field(default=None, min_length=1, max_length=BODY_MAX)
    media_key: str | None = Field(default=None, min_length=1, max_length=200)
    duration_s: int | None = Field(default=None, ge=1, le=60)
    # The price shown for this send (P-56, D-600): compared, never charged.
    shown_price: ShownPrice = 0

    @model_validator(mode="after")
    def _the_kinds_fields(self) -> Self:
        if self.kind is MessageKind.SYSTEM:
            raise ValueError("system messages are the app's, never sent")
        if self.kind is MessageKind.TEXT:
            if self.body is None or not self.body.strip():
                raise ValueError("a text message needs a body")
            if self.media_key is not None or self.duration_s is not None:
                raise ValueError("a text message has no media")
        return self


class ReadRequest(BaseModel):
    """`{up_to_message_id}`: the other person's messages are read up to this
    one, which must be one I can see in the Thread (T-7.5)."""

    model_config = ConfigDict(extra="forbid")

    up_to_message_id: UUID
