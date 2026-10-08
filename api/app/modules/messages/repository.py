"""SQL for messages (T-7.1, T-7.3). No rules here: the services decide."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MessageKind
from app.modules.messages.models import Message


async def add_text(
    session: AsyncSession,
    *,
    thread_id: UUID,
    sender_id: UUID,
    body: str,
    body_raw: str | None,
    masked: bool,
    client_msg_id: UUID,
) -> Message:
    """A text message, written now; its row as stored, `created_at` included."""
    row: Message | None = await session.scalar(
        insert(Message)
        .values(
            thread_id=thread_id,
            sender_id=sender_id,
            kind=MessageKind.TEXT,
            body=body,
            body_raw=body_raw,
            masked=masked,
            client_msg_id=client_msg_id,
        )
        .returning(Message)
    )
    assert row is not None
    return row
