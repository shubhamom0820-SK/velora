"""`auth.pins.pin_problem` (T-3.9): what a PIN may be (D-012, D-069). Pure,
so it is checked against all 10,000 four-digit PINs."""

from __future__ import annotations

import pytest

from app.modules.auth import pins
from seed.data import TEST_WOMAN_PIN

ALL = [f"{n:04d}" for n in range(10_000)]


def _expected_refusals() -> set[str]:
    """D-069's four families, built here from their definitions."""
    repeats = {d * 4 for d in "0123456789"}
    ascending = {"0123456789"[i : i + 4] for i in range(7)}
    runs = ascending | {run[::-1] for run in ascending}
    pairs = {a + b + a + b for a in "0123456789" for b in "0123456789" if a != b}
    return repeats | runs | pairs | set(pins.COMMON_PINS)


def test_exactly_these_pins_are_refused() -> None:
    """Exactly, not at least: a rule that refused more than D-069 says would
    pass any test that only checks what it refuses."""
    refused = {pin for pin in ALL if pins.pin_problem(pin) is not None}

    assert refused == _expected_refusals()
    assert len(refused) == 10 + 14 + 90 + 4  # 1004, 2000, 1122, 2001 only listed


def test_the_seeds_test_woman_pin_passes() -> None:
    """T-1.15 seeds 4829; the rules mustn't break `make seed` the day they land."""
    assert TEST_WOMAN_PIN == "4829"
    assert pins.pin_problem(TEST_WOMAN_PIN) is None


def test_the_common_pins_are_the_studys_top_20_in_its_order() -> None:
    """DataGenetics, read 3 October 2026 (T-3.9): its table, rank 1 to 20."""
    assert pins.COMMON_PINS == (
        "1234", "1111", "0000", "1212", "7777", "1004", "2000", "4444", "2222",
        "6969", "9999", "3333", "5555", "6666", "1122", "1313", "8888", "4321",
        "2001", "1010",
    )  # fmt: skip


@pytest.mark.parametrize(
    ("pin", "problem"),
    [
        ("0000", "is one digit four times"),
        ("7777", "is one digit four times"),
        ("0123", "is a straight run of digits"),
        ("6789", "is a straight run of digits"),
        ("9876", "is a straight run of digits"),
        ("3210", "is a straight run of digits"),
        ("1212", "is a pair of digits, repeated"),
        ("9090", "is a pair of digits, repeated"),
        ("1004", "is one of the most common PINs"),
        ("2000", "is one of the most common PINs"),
        ("1122", "is one of the most common PINs"),
        ("2001", "is one of the most common PINs"),
        ("123", "must be four digits"),
        ("12345", "must be four digits"),
        ("12a4", "must be four digits"),
        ("१२३४", "must be four digits"),  # Devanagari digits: a keypad types ASCII
    ],
)
def test_each_refused_shape_says_why(pin: str, problem: str) -> None:
    assert pins.pin_problem(pin) == problem


@pytest.mark.parametrize(
    "pin", ["4829", "7890", "0987", "1235", "1221", "1100", "2468"]
)
def test_pins_near_a_shape_but_not_in_one_pass(pin: str) -> None:
    """No wrap-around runs, no near-runs, no mirrored pairs: only D-069's."""
    assert pins.pin_problem(pin) is None


def test_no_problem_holds_a_digit_so_none_repeats_a_pin() -> None:
    problems = {pins.pin_problem(pin) for pin in [*ALL, "123", "12345", "12a4"]}

    assert [p for p in problems if p and any(c.isdigit() for c in p)] == []
