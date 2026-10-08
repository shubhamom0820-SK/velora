"""Threads (T-7.1, T-7.6): what opening one costs, how long it lasts, what
buys it time, and who sees what of it. No I/O.

- A Thread from a match lasts `app_config.thread_hours`, read at the moment it
  opens, never a number written here (checklist A): an hour since T-7.6
  (D-097). A private message never expires (D-231, D-550).
- Opening is `thread_open` from a match and `dm_open` for a private message,
  priced by `pricing` (0 for a woman, D-098).
- An expired Thread refuses a man and lets a woman through (D-097): an
  allowlist of who passes, so a gender nobody has named is refused.
- Her message moves a live Thread's hour on, never his (D-097's amendment;
  D-560); expiry is read from the clock, not the status column.
- Her side shows no countdown (D-097, 08-DESIGN §8, D-554): `expires_at` goes
  to a man only, by the same kind of allowlist, and so do the warning and the
  expiry (T-7.6).
- **Time is bought by a man only** (T-7.6): re-open (`thread_reopen`, a fresh
  hour from now) and Extend (`thread_extend`, `thread_extend_hours` on top of
  what is left, and from expired from now; D-250, D-253, D-560). She is never charged and never shown
  either (D-097); a Knot or a private message has no hour to buy (D-642).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from app.core.enums import Gender, LedgerReason, ThreadOrigin, ThreadStatus
from app.core.errors import AppError
from app.modules.threads.models import Thread

THREAD_HOURS_KEY: Final = "thread_hours"
# T-7.6, D-560: what one Extend adds, and how long before expiry he is warned.
THREAD_EXTEND_HOURS_KEY: Final = "thread_extend_hours"
THREAD_WARN_MINUTES_KEY: Final = "thread_warn_minutes"

# The chats list (T-7.2): "Recent" is a message in the last three days, as the
# prototype's Knots filter has it; a row's preview is a text's first 100
# characters.
RECENT_FOR: Final = timedelta(days=3)
PREVIEW_CHARS: Final = 100

OPEN_PRICE: Final = {
    ThreadOrigin.MATCH: LedgerReason.THREAD_OPEN,
    ThreadOrigin.DM: LedgerReason.DM_OPEN,
}


def expires_at(origin: ThreadOrigin, now: datetime, hours: int) -> datetime | None:
    """When a Thread opened now expires: `hours` on from a match, never for a
    private message."""
    if origin is ThreadOrigin.DM:
        return None
    return now + timedelta(hours=hours)


def passes_an_expired_thread(gender: Gender | None) -> bool:
    """Whether this person may still send on an expired Thread: a woman."""
    return gender is Gender.FEMALE


def sees_the_expiry(gender: Gender | None) -> bool:
    """Whether `expires_at` is shown to this person: a man (D-554)."""
    return gender is Gender.MALE


def has_expired(thread: Thread, now: datetime) -> bool:
    """Expired by the clock, not the status column (D-560): an active Thread
    whose `expires_at` has passed is expired for every check, though the cron
    hasn't caught its status up yet (T-7.6)."""
    if thread.status is ThreadStatus.EXPIRED:
        return True
    return (
        thread.status is ThreadStatus.ACTIVE
        and thread.expires_at is not None
        and thread.expires_at <= now
    )


def restarts_the_hour(thread: Thread, gender: Gender | None) -> bool:
    """Whether a message from this person moves a live Thread's hour on: hers
    does, his never does (D-097's amendment, a), and a private message or a
    Knot has no hour."""
    return (
        gender is Gender.FEMALE
        and thread.status is ThreadStatus.ACTIVE
        and thread.origin is ThreadOrigin.MATCH
    )


def thread_expired() -> AppError:
    """His alone (D-097): an expired Thread lets her through."""
    return AppError(
        "THREAD_EXPIRED",
        "This Thread has run out. Re-open it to reply.",
        status=410,
    )


# --- Buying time (T-7.6) -------------------------------------------------------------


def buys_time(gender: Gender | None) -> bool:
    """Whether this person may re-open or Extend a Thread: a man. She is never
    charged and never shown either (D-097), so hers is `NOT_ALLOWED`."""
    return gender is Gender.MALE


def has_an_hour(thread: Thread) -> bool:
    """Whether the Thread runs on an hour at all: one from a match, not knotted.
    A Knot is permanent (D-003) and a private message never expires (D-550)."""
    return (
        thread.origin is ThreadOrigin.MATCH
        and thread.status is not ThreadStatus.KNOTTED
    )


def reopened_until(now: datetime, hours: int) -> datetime:
    """A re-open's hour starts now (T-7.6's answer 1): he paid 2 for an hour."""
    return now + timedelta(hours=hours)


def extended_until(thread: Thread, now: datetime, hours: int) -> datetime:
    """Extend adds to what is left, never from now while time is left (T-7.6's
    answer 4: 4 hours left and an Extend of 24 is 28); from expired, from now
    (D-560)."""
    left_until = thread.expires_at
    start = now if left_until is None or left_until < now else left_until
    return start + timedelta(hours=hours)


def time_event(reason: LedgerReason, thread_id: UUID, key: str) -> str:
    """The wallet's event for a re-open or an Extend bought under the client's
    `Idempotency-Key` (D-077: the key fills only the event): the Thread named
    too, so a key sent again for another Thread is another purchase."""
    kind = "reopen" if reason is LedgerReason.THREAD_REOPEN else "extend"
    return f"{kind}:{thread_id}:{key}"


def not_allowed() -> AppError:
    return AppError("NOT_ALLOWED", "This Thread can't take that.", status=422)
