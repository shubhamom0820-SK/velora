"""`core.clock` is the only clock; rule 7 depends on it behaving exactly."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from app.core import clock


@pytest.fixture(autouse=True)
def _always_unfreeze() -> Iterator[None]:
    yield
    clock.unfreeze()


def test_now_is_timezone_aware_utc() -> None:
    value = clock.now()

    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


def test_freeze_pins_now() -> None:
    at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    clock.freeze(at)

    assert clock.now() == at
    assert clock.now() == at  # stable across calls


def test_advance_moves_frozen_time() -> None:
    clock.freeze(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    clock.advance(timedelta(hours=25))

    assert clock.now() == datetime(2026, 1, 2, 13, 0, tzinfo=UTC)


def test_unfreeze_returns_to_the_wall_clock() -> None:
    clock.freeze(datetime(2020, 1, 1, tzinfo=UTC))

    clock.unfreeze()

    assert clock.now().year >= 2026


def test_freeze_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError):
        clock.freeze(datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001 — naive on purpose


def test_advance_without_freeze_is_an_error() -> None:
    with pytest.raises(RuntimeError):
        clock.advance(timedelta(hours=1))


def test_today_ist_rolls_over_at_1830_utc() -> None:
    """Daily caps reset at midnight IST, which is 18:30 UTC the day before."""
    clock.freeze(datetime(2026, 3, 1, 18, 29, tzinfo=UTC))
    assert clock.today_ist().isoformat() == "2026-03-01"

    clock.freeze(datetime(2026, 3, 1, 18, 30, tzinfo=UTC))
    assert clock.today_ist().isoformat() == "2026-03-02"


def test_today_ist_differs_from_utc_date_late_in_the_day() -> None:
    clock.freeze(datetime(2026, 3, 1, 20, 0, tzinfo=UTC))

    assert clock.now().date().isoformat() == "2026-03-01"
    assert clock.today_ist().isoformat() == "2026-03-02"
