"""Messages (T-7.1 writes the first; T-7.3 the rest).

Every text passes `filters` first: refused for abuse or asking for money
(`MESSAGE_REJECTED`, a `message_rejected` signal kept), then masked in the
Thread's first `mask_first_n_messages` (D-030). A message is written in the
transaction that makes it true, and `message.new` goes to both people, each
seeing it as theirs or not.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.errors import AppError
from app.modules.messages import filters, repository
from app.modules.messages.models import Message as MessageRow
from app.modules.messages.schemas import Message
from app.modules.safety import service as safety_service
from app.modules.threads.models import Thread

MASK_KEY = "mask_first_n_messages"
MESSAGE_NEW = "message.new"


def _rejected(rule: str) -> AppError:
    return AppError(
        "MESSAGE_REJECTED",
        "That message can't be sent.",
        status=422,
        details={"rule": rule},
    )


async def refuse_if_rejected(session: AsyncSession, user_id: UUID, text: str) -> None:
    """Refuse `text` if it breaks a rule, keeping the signal: in a transaction
    of its own, before the send's, so the refusal can't roll it back."""
    rule = filters.refusal(text)
    if rule is None:
        return
    async with session.begin():
        safety_service.record_message_rejected(session, user_id, rule=rule)
    raise _rejected(rule)


async def write_text(
    session: AsyncSession,
    thread: Thread,
    sender_id: UUID,
    text: str,
    client_msg_id: UUID,
    *,
    mask_first_n: int,
) -> MessageRow:
    """`text` in `thread`, masked while the Thread is young, in the caller's
    transaction, which holds the Thread. The Thread counts it."""
    masked = (
        filters.mask(text)
        if thread.message_count < mask_first_n
        else filters.Masked(body=text, masked=False)
    )
    row = await repository.add_text(
        session,
        thread_id=thread.id,
        sender_id=sender_id,
        body=masked.body,
        body_raw=text if masked.masked else None,
        masked=masked.masked,
        client_msg_id=client_msg_id,
    )
    thread.message_count += 1
    thread.last_message_at = row.created_at
    return row


def view_of(
    row: MessageRow,
    viewer_id: UUID,
    *,
    from_deleted_account: bool = False,
    locked: bool = False,
) -> Message:
    """`row` as `viewer_id` sees it. Never `body_raw`."""
    mine = row.sender_id == viewer_id
    return Message(
        id=row.id,
        thread_id=row.thread_id,
        kind=row.kind,
        body=row.body,
        masked=row.masked,
        duration_s=row.duration_s,
        mine=mine,
        from_deleted_account=from_deleted_account,
        locked=locked,
        read_at=row.read_at,
        created_at=row.created_at,
        client_msg_id=row.client_msg_id if mine else None,
    )


def announce(session: AsyncSession, row: MessageRow, recipient_id: UUID) -> None:
    """`message.new` to both people, each with their own view of it."""
    for user_id in (row.sender_id, recipient_id):
        events.queue(
            session,
            user_id,
            MESSAGE_NEW,
            {
                "thread_id": str(row.thread_id),
                "message": view_of(row, user_id).model_dump(mode="json"),
            },
        )
