"""Gifts' rules with no database (T-8.9): the week from Monday 00:00 IST
(D-650), the free sends then the row's price (D-231), and the cooldown's
seconds, rounded up."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.gifts import rules

# Monday 12 October 2026, 00:00 IST.
MONDAY = datetime(2026, 10, 11, 18, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "start"),
    [
        (MONDAY, MONDAY),
        (MONDAY - timedelta(microseconds=1), MONDAY - timedelta(days=7)),
        (MONDAY + timedelta(days=6, hours=23, minutes=59), MONDAY),
        # 23:00 UTC on Sunday is already Monday in India.
        (datetime(2026, 10, 11, 23, 0, tzinfo=UTC), MONDAY),
        (datetime(2026, 10, 11, 18, 0, tzinfo=UTC), MONDAY - timedelta(days=7)),
    ],
)
def test_the_week_starts_monday_at_midnight_ist(now: datetime, start: datetime) -> None:
    assert rules.week_start(now) == start
    assert rules.next_week_start(now) == start + timedelta(days=7)
    assert rules.next_week_start(now).tzinfo is UTC


@pytest.mark.parametrize(
    ("used", "limit", "price"),
    [(0, 15, 0), (14, 15, 0), (15, 15, 10), (16, 15, 10), (0, 0, 10)],
)
def test_free_while_they_last_then_the_rows_price(
    used: int, limit: int, price: int
) -> None:
    assert rules.price_of(10, free_used=used, free_limit=limit) == price
    assert rules.free_left(used, limit) == max(limit - used, 0)


@pytest.mark.parametrize(
    ("since", "left"),
    [
        (None, 0),
        (timedelta(0), 86_400),
        (timedelta(hours=23, minutes=59, seconds=59, microseconds=1), 1),
        (timedelta(hours=24), 0),
        (timedelta(hours=25), 0),
    ],
)
def test_the_cooldown_is_whole_seconds_rounded_up(
    since: timedelta | None, left: int
) -> None:
    last = None if since is None else MONDAY - since
    assert rules.cooldown_left(last, MONDAY, 24) == left
