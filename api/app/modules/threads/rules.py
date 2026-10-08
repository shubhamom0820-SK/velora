"""Threads (T-7.1): what opening one costs, how long it lasts, and who sees
what of it. No I/O.

- A Thread from a match lasts `app_config.thread_hours`, read at the moment it
  opens, never a number written here (checklist A): 24 today, the 1-hour
  Thread's when P-150 changes the setting (D-097). A private message never
  expires (D-231, D-550).
- Opening is `thread_open` from a match and `dm_open` for a private message,
  priced by `pricing` (0 for a woman, D-098).
- An expired Thread refuses a man and lets a woman through (D-097): an
  allowlist of who passes, so a gender nobody has named is refused.
- Her side shows no countdown (D-097, 08-DESIGN §8, D-554): `expires_at` goes
  to a man only, by the same kind of allowlist.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from app.core.enums import Gender, LedgerReason, ThreadOrigin

THREAD_HOURS_KEY: Final = "thread_hours"

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
