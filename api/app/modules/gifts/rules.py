"""The rules of gifts that need no database (T-8.9).

- **The week starts Monday 00:00 IST** (D-650): a calendar week, as a user in
  India lives it, so "free sends left this week" has one reset time to show.
- **Fifteen free sends a week, then each costs its gift's price** (D-231).
  Never refused for the count: the sixteenth is paid, so `GIFT_LIMIT_REACHED`
  keeps no case (D-650).
- **The same gift to the same woman waits `gift_same_recipient_cooldown_h`**
  (D-016), free or paid: `GIFT_COOLDOWN`, with the seconds left.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, time, timedelta

from app.core.clock import IST
from app.core.errors import AppError

FREE_WEEKLY_KEY = "gift_free_weekly_limit"
COOLDOWN_KEY = "gift_same_recipient_cooldown_h"


def week_start(now: datetime) -> datetime:
    """The Monday 00:00 IST at or before `now` (D-650)."""
    today = now.astimezone(IST).date()
    monday = today - timedelta(days=today.weekday())
    return datetime.combine(monday, time(0), tzinfo=IST)


def next_week_start(now: datetime) -> datetime:
    """When this week's free sends come back: the next Monday 00:00 IST, in
    UTC, as the API writes every time (02-ARCHITECTURE §3)."""
    return (week_start(now) + timedelta(days=7)).astimezone(UTC)


def price_of(credits: int, *, free_used: int, free_limit: int) -> int:
    """What this send costs: 0 while this week's free sends last, then the
    gift row's own price (D-231)."""
    return 0 if free_used < free_limit else credits


def free_left(free_used: int, free_limit: int) -> int:
    return max(free_limit - free_used, 0)


def cooldown_left(last_sent: datetime | None, now: datetime, hours: int) -> int:
    """Seconds until the same gift may go to the same woman again; 0 if now.
    Rounded up, so waiting what it says is always enough."""
    if last_sent is None:
        return 0
    left = last_sent + timedelta(hours=hours) - now
    if left <= timedelta(0):
        return 0
    return math.ceil(left.total_seconds())


def cooldown(retry_after_s: int) -> AppError:
    return AppError(
        "GIFT_COOLDOWN",
        "You sent her this gift recently. Try another, or send it again later.",
        status=429,
        details={"retry_after_s": retry_after_s},
    )
