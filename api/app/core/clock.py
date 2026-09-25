"""The only way application code reads the current time (CLAUDE.md rule 7).

Never call `datetime.now()` anywhere else. Routing every read through one
function is what lets tests freeze and advance time to exercise thread expiry,
OTP windows and daily caps without sleeping.

Timestamps are stored and compared in UTC; only display is IST (D-029).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# When set, `now()` returns this instead of the wall clock. Tests own this via
# the helpers below; application code must never touch it.
_override: datetime | None = None


def now() -> datetime:
    """The current instant as a timezone-aware UTC datetime."""
    if _override is not None:
        return _override
    return datetime.now(UTC)  # noqa: TID251 — the one sanctioned wall-clock read


def today_ist() -> date:
    """Today's date in IST.

    Daily caps and "resets at midnight" are what a user in India experiences,
    so they roll over at 00:00 IST — 18:30 the previous day in UTC.
    """
    return now().astimezone(IST).date()


def freeze(at: datetime) -> None:
    """Pin `now()` to a fixed instant. Test-only."""
    global _override
    if at.tzinfo is None:
        raise ValueError("freeze() needs a timezone-aware datetime")
    _override = at.astimezone(UTC)


def advance(by: timedelta) -> datetime:
    """Move frozen time forward. Test-only; requires `freeze()` first."""
    global _override
    if _override is None:
        raise RuntimeError("advance() requires freeze() first")
    _override = _override + by
    return _override


def unfreeze() -> None:
    """Return to the wall clock. Test-only."""
    global _override
    _override = None
