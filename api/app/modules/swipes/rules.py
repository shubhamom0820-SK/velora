"""Swipes (T-6.4): what counts toward men's daily cap, and when it resets.
No I/O.

Swiping is free either way (D-098); a Super Like is its own action, 5 Velas for
a man and nothing for a woman (D-250, D-002), and doesn't count toward the cap
(D-492). The cap is a man's alone, `app_config`'s `swipe_daily_limit_men`, by
the IST day: what a man in India experiences as "today".
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Final

from app.core.clock import IST
from app.core.enums import Gender, SwipeDirection

DAILY_CAP_KEY: Final = "swipe_daily_limit_men"
# D-492: like and pass count; a Super Like, paid, doesn't.
COUNTED: Final = frozenset({SwipeDirection.LIKE, SwipeDirection.PASS})
# A like or a Super Like, returned, is a match.
LIKES: Final = frozenset({SwipeDirection.LIKE, SwipeDirection.SUPER})


def capped(gender: Gender | None) -> bool:
    """Whether this person has a daily cap at all: men only."""
    return gender is Gender.MALE


def counts(direction: SwipeDirection) -> bool:
    return direction in COUNTED


def resets_at(day: date) -> datetime:
    """When `day`'s count ends: the next IST midnight."""
    return datetime.combine(day + timedelta(days=1), time(0), tzinfo=IST)
