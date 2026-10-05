"""T-4.8's rules alone (D-310): completeness by photo, who may finish without a
match, and the requirements' order."""

from __future__ import annotations

from dataclasses import replace
from typing import get_args

import pytest

from app.core.enums import Gender, Seeking
from app.modules.onboarding import rules

READY = rules.Facts(
    seeking=Seeking.WOMEN,
    intents=1,
    first_name="Test",
    hometown="Jalandhar",
    city="Phagwara",
    located=True,
    username="ready",
    about="A profile ready to finish, with an about long enough to pass.",
    approved_photos=1,
    interests=5,
)


@pytest.mark.parametrize(
    ("photos", "completeness"),
    [(1, 50), (2, 60), (3, 70), (4, 80), (5, 90), (6, 100), (7, 100)],
)
def test_completeness_is_50_and_10_for_each_photo_after_the_first(
    photos: int, completeness: int
) -> None:
    assert rules.completeness(photos) == completeness


def test_a_ready_profile_misses_nothing() -> None:
    assert rules.missing(READY) == []


@pytest.mark.parametrize("intents", [1, 2, 3])
def test_one_to_three_intents_are_enough(intents: int) -> None:
    assert rules.missing(replace(READY, intents=intents)) == []


def test_nothing_at_all_misses_everything_in_onboardings_order() -> None:
    empty = rules.Facts(
        seeking=None,
        intents=0,
        first_name=None,
        hometown=None,
        city=None,
        located=False,
        username=None,
        about=None,
        approved_photos=0,
        interests=0,
    )
    assert rules.missing(empty) == list(get_args(rules.Missing))


def test_an_empty_string_is_missing_too() -> None:
    blank = replace(READY, first_name="", hometown="", city="", username="", about="")
    assert rules.missing(blank) == [
        "first_name",
        "hometown",
        "city",
        "username",
        "about",
    ]


@pytest.mark.parametrize(
    ("gender", "needs"),
    [(Gender.MALE, False), (Gender.FEMALE, True), (None, True)],
    ids=["man", "woman", "no gender"],
)
def test_only_a_man_finishes_without_a_match(
    gender: Gender | None, needs: bool
) -> None:
    assert rules.needs_a_match(gender) is needs


def test_every_gender_but_male_needs_a_match() -> None:
    """An allowlist: a gender added to the enum later needs a match until
    someone decides otherwise."""
    assert {g for g in Gender if not rules.needs_a_match(g)} == {Gender.MALE}
