"""What a message may say (D-030, D-552): the prototype's lists, refused or
masked, and the sentences its first version caught that it mustn't."""

from __future__ import annotations

import pytest

from app.modules.messages import filters


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        # +91 numbers, with and without spaces or dashes.
        ("call +91 98765 43210", "call ••••••••••••"),
        ("9876543210", "••••••••••"),
        ("98765-43210 any time", "••••••••••• any time"),
        # Spaced digits.
        ("9 8 7 6 5 4 3 2 1 0", "••••••••••••"),
        # Emails and UPI handles: anything@something.
        ("mail priya.k@gmail.com", "mail ••••••••••••"),
        ("pay priya@ybl", "pay •••••••••"),
        ("priya@okhdfcbank", "••••••••••••"),
        # Social handles: the app named, a separator, the handle.
        ("insta: x", "••••••••"),
        ("my insta is priya_23", "my ••••••••••••"),
        ("snap @priya", "•••••••••••"),
        ("telegram - priya", "••••••••••••"),
        ("insta id priya.k", "••••••••••••"),
    ],
)
def test_contact_details_are_masked(text: str, shown: str) -> None:
    assert filters.mask(text) == filters.Masked(body=shown, masked=True)


@pytest.mark.parametrize(
    "text",
    [
        "I was watching water polo",  # the prototype's `wa` caught both
        "send it on whatsapp",
        "2010-2015 was a good run",  # nine characters, a span of years
        "I snapped a photo",
        "see you at 7:30",
        "Hello!",
    ],
)
def test_ordinary_sentences_are_left_alone(text: str) -> None:
    assert filters.mask(text) == filters.Masked(body=text, masked=False)


def test_the_known_cost_of_naming_an_app_then_is() -> None:
    """ "my insta is priya_23" is masked, so "whatsapp is down" is too: in a
    Thread's first 20 messages only, and accepted (D-552)."""
    assert filters.mask("whatsapp is down").masked


def test_a_long_match_is_twelve_dots_at_most() -> None:
    masked = filters.mask("write to someone.with.a.long.name@example.co.in")
    assert masked.body == "write to " + filters.MASK * filters.MASK_MAX


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("you bitch", "abuse"),
        ("chutiya", "abuse"),
        ("RANDI", "abuse"),
        ("send money first", "solicitation"),
        ("send me some money", "solicitation"),
        ("paytm me", "solicitation"),
        ("gpay kar do", "solicitation"),
        ("phonepe pe bhejo", "solicitation"),
        ("transfer me 500 rupees", "solicitation"),
        ("send 5,000 rs", "solicitation"),
        ("transfer money now", "solicitation"),
        ("money transfer please", "solicitation"),
        ("upi id do", "solicitation"),
        ("what's your upi id", "solicitation"),
        ("western union works", "solicitation"),
    ],
)
def test_abuse_and_asking_for_money_are_refused(text: str, rule: str | None) -> None:
    assert filters.refusal(text) == rule


@pytest.mark.parametrize(
    "text",
    [
        "I'm transferring jobs next month",
        "I got a transfer to Pune",  # the bare word, refused before D-552
        "the upi outage was annoying",
        "grape juice",
        "therapist",
        "Hello!",
    ],
)
def test_ordinary_sentences_are_not_refused(text: str) -> None:
    assert filters.refusal(text) is None


def test_abuse_is_named_before_money() -> None:
    assert filters.refusal("bitch, send money") == "abuse"
