"""Fraud scoring v1's rules (T-9.2, D-031, D-900, D-901): the weights, caps,
decay and bands as the founder decided them, each a literal here, so a
quiet change to `fraud.py` turns this red (06-TESTING: fraud weights)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.enums import FraudBand
from app.modules.safety import fraud
from app.modules.safety.fraud import Event

NEW = timedelta(0)


def _many(signal: str, weight: int, n: int = 50) -> list[Event]:
    return [Event(signal, weight, NEW) for _ in range(n)]


def test_the_weights_and_caps_are_the_founders() -> None:
    assert dict(fraud.WEIGHTS) == {
        "report_received": 20,
        "contact_masked": 2,
        "many_new_threads": 25,
        "identical_first_message": 25,
        "many_sign_ins": 15,
        "location_jump": 15,
        "possible_minor_photo_score": 10,
        "chargeback_shortfall": 30,
    }
    assert dict(fraud.REJECTED_WEIGHTS) == {"abuse": 10, "solicitation": 15}
    assert dict(fraud.CAPS) == {
        "message_rejected": 45,
        "contact_masked": 10,
        "many_new_threads": 25,
        "identical_first_message": 25,
        "many_sign_ins": 15,
        "location_jump": 30,
        "possible_minor_photo_score": 20,
        "chargeback_shortfall": 30,
    }
    assert "report_received" not in fraud.CAPS


def test_the_thresholds_are_the_plans() -> None:
    assert (fraud.NEW_THREADS_MAX, fraud.NEW_THREADS_WINDOW) == (
        30,
        timedelta(hours=24),
    )
    assert (fraud.IDENTICAL_MAX, fraud.IDENTICAL_WINDOW) == (10, timedelta(days=7))
    assert (fraud.SIGN_INS_MAX, fraud.SIGN_INS_WINDOW) == (3, timedelta(days=7))
    assert (fraud.JUMP_KM, fraud.JUMP_WITHIN) == (500, timedelta(hours=1))
    assert (fraud.REPORTS_TO_FREEZE, fraud.REPORTS_WINDOW) == (3, timedelta(hours=24))
    assert fraud.ONCE_PER == timedelta(hours=24)


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0, FraudBand.NORMAL),
        (29, FraudBand.NORMAL),
        (30, FraudBand.MONITOR),
        (59, FraudBand.MONITOR),
        (60, FraudBand.SHADOW),
        (80, FraudBand.SHADOW),
        (81, FraudBand.FREEZE),
        (100, FraudBand.FREEZE),
    ],
)
def test_the_bands_are_d031s_with_60_and_80_shadow(score: int, band: FraudBand) -> None:
    assert fraud.band(score) is band


@pytest.mark.parametrize(
    ("numbers", "band"), [(2, FraudBand.NORMAL), (3, FraudBand.FREEZE)]
)
def test_three_reporting_numbers_freeze_whatever_the_score(
    numbers: int, band: FraudBand
) -> None:
    assert fraud.band(0, reporting_numbers=numbers) is band


@pytest.mark.parametrize(
    ("age", "left"),
    [
        (timedelta(0), 20.0),
        (timedelta(days=3, hours=12), 10.0),
        (timedelta(days=7), 0.0),
        (timedelta(days=9), 0.0),
        (-timedelta(minutes=5), 20.0),
    ],
)
def test_an_event_decays_in_a_straight_line_to_nothing_at_seven_days(
    age: timedelta, left: float
) -> None:
    assert fraud.decayed(20, age) == pytest.approx(left)


def test_each_signal_is_held_to_its_cap() -> None:
    scored = fraud.score(
        _many("contact_masked", 2)
        + _many("message_rejected", 15)
        + _many("location_jump", 15)
    )
    assert scored.signals == {
        "contact_masked": 10,
        "location_jump": 30,
        "message_rejected": 45,
    }
    assert scored.score == 85


def test_a_report_counts_once_per_reporter_and_has_no_cap() -> None:
    same = [Event("report_received", 20, NEW, reporter="a") for _ in range(5)]
    assert fraud.score(same).score == 20
    five = [Event("report_received", 20, NEW, reporter=r) for r in "abcde"]
    scored = fraud.score(five)
    assert (scored.score, fraud.band(scored.score)) == (100, FraudBand.FREEZE)
    four = five[:4]
    assert fraud.band(fraud.score(four).score) is FraudBand.SHADOW


@pytest.mark.parametrize("signal", sorted(fraud.CAPS))
def test_no_signal_but_reports_reaches_shadow_on_its_own(signal: str) -> None:
    """D-900's promise: only people's reports take someone out of everyone's
    deck or freeze them; every other signal, however often, stops below."""
    scored = fraud.score(_many(signal, 99))
    assert scored.score < fraud.SHADOW_FROM


def test_a_possible_minor_never_leaves_the_normal_band_on_its_own() -> None:
    """D-093: a model's score weighs in, and never acts on anyone alone."""
    assert fraud.band(fraud.score(_many("possible_minor_photo_score", 10)).score) is (
        FraudBand.NORMAL
    )


def test_a_chargeback_never_passes_monitor_on_its_own() -> None:
    """D-520: a dispute may be his bank's mistake."""
    assert fraud.band(fraud.score(_many("chargeback_shortfall", 30)).score) is (
        FraudBand.MONITOR
    )


def test_an_unknown_signal_stays_under_monitor() -> None:
    assert fraud.score(_many("a_later_tasks_signal", 50)).score < fraud.MONITOR_FROM


def test_the_score_is_held_to_100() -> None:
    reports = [Event("report_received", 20, NEW, reporter=n) for n in range(9)]
    assert fraud.score(reports).score == 100


def test_a_jump_is_more_than_500_km_within_an_hour() -> None:
    hour = timedelta(hours=1)
    assert fraud.jumped(501, hour)
    assert not fraud.jumped(500, hour)
    assert not fraud.jumped(501, hour + timedelta(seconds=1))
