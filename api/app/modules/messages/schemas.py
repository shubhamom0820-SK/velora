"""A message as its reader sees it (04-API.md, T-7.1 and T-7.3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import MessageKind


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
