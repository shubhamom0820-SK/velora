"""Messages (T-7.3): what a send costs him, and what a voice note hides. No I/O.

- **His first message in a Thread he didn't open** (D-097, D-250): she has
  written → the 2-Vela re-open, `thread_reopen`, keyed once per Thread; she
  hasn't → `thread_open`'s 5, since a man's first message opens a Thread.
  Once he has written, nothing more, until it expires. The opener paid to open.
- **A private message** (D-231, D-550): every message of his costs
  `dm_message`, the message as its ref, until the Thread is knotted.
- Knots are free (D-003). A woman's price is 0 for everything (D-098):
  `pricing` decides that, never this module.
- **A voice note is locked** for a man who hasn't unlocked it, and never for
  its sender (T-7.9 sells the unlock): an allowlist of who hears free.
- **Only a woman sends one** (D-010): an allowlist, so a man and anyone with
  no gender are refused alike.
"""

from __future__ import annotations

from uuid import UUID

from app.core.enums import Gender, LedgerReason, MessageKind, ThreadOrigin, ThreadStatus
from app.modules.messages.models import Message
from app.modules.threads.models import Thread


def answer_price(
    thread: Thread, sender_id: UUID, *, wrote: bool, they_wrote: bool
) -> LedgerReason | None:
    """What his first message costs in a Thread from a match he didn't open,
    or None: nothing to pay."""
    if (
        thread.origin is not ThreadOrigin.MATCH
        or thread.status is ThreadStatus.KNOTTED
        or thread.opened_by == sender_id
        or wrote
    ):
        return None
    return LedgerReason.THREAD_REOPEN if they_wrote else LedgerReason.THREAD_OPEN


def answer_event(thread_id: UUID) -> str:
    """The wallet's event for answering her, once per Thread: `thread_reopen`
    repeats for one Thread (T-7.6's re-opens), so the caller names it."""
    return f"answer:{thread_id}"


def private_message_priced(thread: Thread) -> bool:
    """Whether each of his messages here costs `dm_message`."""
    return (
        thread.origin is ThreadOrigin.DM and thread.status is not ThreadStatus.KNOTTED
    )


def locked_for(
    message: Message, viewer_id: UUID, gender: Gender | None, unlocked: bool
) -> bool:
    """Whether `viewer_id` must unlock this voice note before hearing it."""
    if message.kind is not MessageKind.VOICE or message.sender_id == viewer_id:
        return False
    return gender is not Gender.FEMALE and not unlocked


def may_send_voice(gender: Gender | None) -> bool:
    """Whether someone of this gender may send a voice note (D-010)."""
    return gender is Gender.FEMALE
