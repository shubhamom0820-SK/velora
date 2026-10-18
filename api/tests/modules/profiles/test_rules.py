"""`profiles.rules` (T-3.7): what a first name, a place, an about and a
username may be; and (T-4.10) where a position may be and when a location is
current. Pure functions, each rule tested both ways."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.profiles import rules

# --- First name: letters in any script --------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "हरप्रीत",  # Harpreet, Devanagari: a virama and a vowel sign
        "अनन्या",
        "ਗੁਰਪ੍ਰੀਤ",  # Gurpreet, Gurmukhi
        "ਹਰਪ੍ਰੀਤ ਕੌਰ",  # Harpreet Kaur
        "ਸਿੰਘ",  # Singh: a vowel sign before its letter in reading order, and a tippi
        "ரவி",  # Tamil
        "মৌমিতা",  # Bengali
        "محمد",  # Urdu
        "Anne Marie",
        "O'Brien",
        "D’Souza",  # the apostrophe a phone's keyboard types
        "Mary-Jane",
        "Zoë",
        "A",
        "A" * 30,
    ],
)
def test_a_first_name_of_letters_in_any_script_is_accepted(name: str) -> None:
    assert rules.first_name_problem(rules.clean_text(name)) is None


@pytest.mark.parametrize(
    ("name", "problem"),
    [
        ("", "must be 1 to 30 characters"),
        ("A" * 31, "must be 1 to 30 characters"),
        ("Ravi  Kumar", "has two spaces in a row"),
        ("Ravi2", "letters"),
        ("रवि१", "letters"),  # a Devanagari digit is a digit, not a letter
        ("Ravi😀", "letters"),
        ("R@vi", "letters"),
        ("Ravi_K", "letters"),
        ("-Ravi", "letters"),
        ("Ravi-", "letters"),
        ("'Ravi", "letters"),
        ("Ravi--Kumar", "letters"),
        ("Ravi - Kumar", "letters"),
        ("ि", "letters"),  # a vowel sign with no letter to carry it
        ("Ravi\u200dKumar", "letters"),  # a zero-width joiner hides in a name
        ("Ravi\tKumar", "letters"),
        ("Ravi\u00a0Kumar", "letters"),  # a no-break space isn't a single space
    ],
)
def test_a_first_name_breaking_a_rule_is_refused(name: str, problem: str) -> None:
    found = rules.first_name_problem(rules.clean_text(name))
    assert found is not None and problem in found


def test_a_first_name_is_measured_trimmed_and_in_nfc() -> None:
    # "é" typed as e and a combining accent: one character once composed.
    decomposed = "  Rene\u0301e  "
    cleaned = rules.clean_text(decomposed)

    assert cleaned == "Renée" and len(cleaned) == 5
    assert rules.first_name_problem(cleaned) is None
    assert rules.first_name_problem(rules.clean_text(" " + "A" * 30 + " ")) is None


# --- Hometown and city ---------------------------------------------------------------


@pytest.mark.parametrize(
    "place", ["Phagwara", "Sri Ganganagar", "St. Thomas Mount", "ਫਗਵਾੜਾ", "X" * 40]
)
def test_a_place_up_to_40_characters_is_accepted(place: str) -> None:
    assert rules.place_problem(place) is None


@pytest.mark.parametrize(
    ("place", "problem"),
    [
        ("", "must be 1 to 40 characters"),
        ("X" * 41, "must be 1 to 40 characters"),
        ("Phagwara\nPunjab", "can't hold control characters"),
        ("Phag\x00wara", "can't hold control characters"),
        ("Phag\u200bwara", "can't hold control characters"),
    ],
)
def test_a_place_breaking_a_rule_is_refused(place: str, problem: str) -> None:
    assert rules.place_problem(place) == problem


# --- About: length, links, phone numbers ----------------------------------------------

LONG_ENOUGH = "I love long walks around the canal and good chai. "


@pytest.mark.parametrize("length", [0, 1, 39, 300])
def test_an_about_of_up_to_300_characters_is_accepted_none_included(
    length: int,
) -> None:
    """Optional (D-951): none, a word, or anything up to 300."""
    assert rules.about_problem("x" * length) is None


def test_an_about_of_301_characters_is_refused() -> None:
    assert rules.about_problem("x" * 301) == "must be at most 300 characters"


def test_an_about_may_have_lines_but_no_other_control_character() -> None:
    assert rules.about_problem(LONG_ENOUGH + "\nAnd films.") is None
    assert rules.about_problem(LONG_ENOUGH + "\x07") == "can't hold control characters"


@pytest.mark.parametrize(
    "about",
    [
        "9876543210",
        "98765 43210",
        "+91 98765 43210",
        "Call me on 98765 43210",
        "My number is 98765-43210, call after six.",
        "Dial 98765.43210 any time.",
        "9876-543-210",  # ten digits, two separators
        "Reach me: ९८७६५४३२१०",  # Devanagari digits are digits
        "1234567890123",
    ],
)
def test_an_about_with_a_phone_number_is_refused(about: str) -> None:
    assert rules.has_phone_number(about)
    assert rules.about_problem(LONG_ENOUGH + about) == "can't hold a phone number"


@pytest.mark.parametrize(
    "about",
    [
        "I lived in Delhi 2010-2015",
        "I was born in 1998 and moved here in 2015",
        "987654321",  # nine digits
        "98 765 43 210",  # ten digits, but three separators
        "Call me on 98765 - 43210",  # three separator characters break the run
        "Born 01.02.1998, moved 2015.",
    ],
)
def test_digits_that_arent_a_phone_number_are_allowed(about: str) -> None:
    """D-068's answers: a run of 10 or more digits with at most two
    separators inside it, never digits scattered across a sentence."""
    assert not rules.has_phone_number(about)
    assert rules.about_problem(LONG_ENOUGH + about) is None


@pytest.mark.parametrize(
    "about",
    [
        "Find me on www.example",
        "https://example.org/me",
        "HTTP://EXAMPLE.ORG",
        "Instagram: instagram.com/ravi",
        "on insta.com",
        "bit.ly/abc123",
        "wa.me/919876543210",
        "t.me/ravi",
        "x.com/ravi",
        "youtu.be/abc",
        "linktr.ee/ravi",
        "mail me at ravi@gmail.com",
        "my site is ravi.co.in",
    ],
)
def test_an_about_with_a_link_is_refused(about: str) -> None:
    assert rules.about_problem(LONG_ENOUGH + about) == "can't hold a link"


@pytest.mark.parametrize(
    "about",
    [
        "I did my B.Com and then a B.Tech in Jalandhar.",
        "I love music.Also dogs, obviously.",
        "I drink chai.In the evenings I walk.",  # a missed space, not a link
        "Love dogs.Me too, my friends say.",
        "Mr. Bean is my spirit animal, e.g. on Mondays.",
        "A Ph.D. in chai and a M.Sc in films.",
    ],
)
def test_ordinary_writing_isnt_taken_for_a_link(about: str) -> None:
    assert rules.about_problem(LONG_ENOUGH + about) is None


# --- Usernames ---------------------------------------------------------------------


def test_the_reserved_list_is_exactly_the_plans() -> None:
    """D-068's list, word for word: a name added or dropped here must be a
    decision, not an edit."""
    assert rules.RESERVED_USERNAMES == {
        "admin", "administrator", "mod", "moderator", "support", "help",
        "helpdesk", "staff", "team", "official", "root", "system", "security",
        "api", "www", "mail", "billing", "payments", "legal", "privacy",
        "terms", "grievance", "knot", "knots", "thread", "threads", "vela",
        "velas", "me", "null", "undefined",
    }  # fmt: skip


@pytest.mark.parametrize(
    "name",
    ["admin", "ADMIN", "ad.min", "a_d.m_i_n", "_admin_", "a.p.i", "help.desk", "m.e"],
)
def test_reserved_names_match_ignoring_case_dots_and_underscores(name: str) -> None:
    assert rules.is_reserved(name)


@pytest.mark.parametrize("name", ["admin1", "admins", "theadmin", "ravi", "velora_fan"])
def test_names_that_only_contain_a_reserved_one_are_not_reserved(name: str) -> None:
    assert not rules.is_reserved(name)


def test_the_brand_is_reserved_from_app_name_so_a_rename_moves_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert rules.is_reserved("velora") and rules.is_reserved("Ve.Lo_Ra")

    monkeypatch.setattr(rules, "APP_NAME", "Zarina")

    assert rules.is_reserved("zarina")
    assert not rules.is_reserved("velora")


@pytest.mark.parametrize(
    "name",
    ["r\u0430vi_k", "\u0440avi_k", "ravi_\uff4b", "ravi\u2024k"],
    ids=["Cyrillic a", "Cyrillic r", "full-width k", "one-dot leader"],
)
def test_a_username_in_look_alike_letters_is_refused(name: str) -> None:
    """Load-bearing (P-59): an @username reads as exactly one account's, which
    a first name in look-alike letters doesn't."""
    assert not name.isascii()
    assert rules.username_problem(name.lower()) is not None


@pytest.mark.parametrize("name", ["ravi", "ravi.k_99", "a" * 20, "____"])
def test_a_username_in_the_format_is_accepted(name: str) -> None:
    assert rules.username_problem(name) is None


@pytest.mark.parametrize(
    "name", ["rav", "a" * 21, "Ravi", "ravi k", "ravi-k", "रवि", ""]
)
def test_a_username_outside_the_format_is_refused(name: str) -> None:
    assert rules.username_problem(name) == "must be 4 to 20 of a-z, 0-9, '.' and '_'"


# --- Location (T-4.10, D-220) ------------------------------------------------------


@pytest.mark.parametrize(
    ("lat", "lng"),
    [
        (31.2240, 75.7708),  # Phagwara
        (6.75, 93.83),  # Indira Point, the southernmost
        # Each of the mainland's four extents the box is drawn from.
        (37.1, 75.0),
        (8.07, 77.55),
        (24.0, 68.12),
        (28.0, 97.42),
        # Its corners.
        (6.5, 68.0),
        (37.5, 97.5),
    ],
)
def test_a_position_inside_indias_box_has_no_problem(lat: float, lng: float) -> None:
    assert rules.position_problems(lat, lng) == {}


@pytest.mark.parametrize(
    ("lat", "lng", "fields"),
    [
        (6.4999, 75.0, {"lat"}),
        (37.5001, 75.0, {"lat"}),
        (20.0, 67.9999, {"lng"}),
        (20.0, 97.5001, {"lng"}),
        (-31.2, -75.7, {"lat", "lng"}),  # a sign lost
        (75.7, 31.2, {"lat", "lng"}),  # the two swapped
    ],
)
def test_a_position_outside_indias_box_names_each_coordinate(
    lat: float, lng: float, fields: set[str]
) -> None:
    problems = rules.position_problems(lat, lng)

    assert set(problems) == fields
    assert problems.get("lat", "must be inside India, 6.5 to 37.5") == (
        "must be inside India, 6.5 to 37.5"
    )
    assert problems.get("lng", "must be inside India, 68.0 to 97.5") == (
        "must be inside India, 68.0 to 97.5"
    )


def test_the_box_is_known_to_hold_some_neighbours_too() -> None:
    """A box can't follow a border (D-220): these pass, and that is known."""
    for lat, lng in [(27.7172, 85.3240), (23.8103, 90.4125), (6.9271, 79.8612)]:
        assert rules.position_problems(lat, lng) == {}  # Kathmandu, Dhaka, Colombo


NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def test_a_location_is_none_until_set_then_fresh_then_stale_past_six_hours() -> None:
    six = rules.LOCATION_FRESH_FOR
    assert six == timedelta(hours=6)
    assert rules.location_state(None, NOW) == "none"
    assert rules.location_state(NOW, NOW) == "fresh"
    assert rules.location_state(NOW - six, NOW) == "fresh"
    assert rules.location_state(NOW - six - timedelta(microseconds=1), NOW) == "stale"
    # Set "later" than the server's now, as a stored time never is: still fresh.
    assert rules.location_state(NOW + timedelta(hours=1), NOW) == "fresh"
