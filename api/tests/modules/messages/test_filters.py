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


# P-450 (D-981): the founder's Hindi and Hinglish list. Every entry caught, and
# beside it the ordinary sentence it must not catch.
@pytest.mark.parametrize(
    "text",
    [
        # Romanised, as prefixes.
        "bhenchod",
        "bhen chod",
        "behen ke laude",
        "maa ke lode",
        "maderchod",
        "bhosdike",
        "bhosadi wala",
        "haramzada",
        "haramkhor",
        "chinal",
        "chhinal",
        "chinaal",
        # Romanised, as whole words.
        "gandu",
        "gaandu",
        "teri gaand",
        "lauda",
        "lawda",
        "lavda",
        "laude",
        "lodu",
        "lund",
        "harami",
        "jhaantu",
        "jhantu",
        "bsdk",
        "BKL",
        "mkc",
        # Devanagari.
        "मादरचोद",
        "बहनचोद",
        "बहेनचोद",
        "भेनचोद",
        "तू चूतिया है",
        "चुतिया",
        "भोसड़ी के",
        "भोसडी",
        "हरामज़ादा",
        "हरामजादा",
        "हरामखोर",
        "छिनाल",
        "रंडी",
        "गांडू",
        "गाँडू",
        "गाण्डू",
        "तेरी गांड",
        "लौड़ा",
        "लौडा",
        "लंड",
        "हरामी",
        "झांटू",
    ],
)
def test_the_founders_abuse_words_are_refused(text: str) -> None:
    assert filters.refusal(text) == "abuse"


@pytest.mark.parametrize(
    "text",
    [
        # Apps.
        "google pay kar do",
        "amazon pay pe bhejo",
        "mobikwik number",
        "freecharge se",
        "bhim upi pe",
        "पेटीएम कर दो",
        "गूगल पे",
        "फोनपे पे भेजो",
        "यूपीआई दो",
        # The money, then the ask.
        "paise bhejo",
        "paise bhej do",
        "paisa de do",
        "paise dedo",
        "paise do na",
        "paise chahiye",
        "rupaye bhejo",
        "500 rupees bhejna",
        "पैसे भेजो",
        "पैसे भेज दो",
        "पैसे चाहिए",
        "रुपये भेजो",
        # An amount, then "send".
        "500 bhejo",
        "₹2000 bhej do",
        "५०० भेजो",
        # A recharge.
        "recharge kar do",
        "recharge kara do",
        "recharge karwa do",
        "mera recharge kar dena",
        "recharge kar doge?",
        "रिचार्ज कर दो",
        # A loan.
        "udhaar de do",
        "udhaar chahiye",
        "उधार दे दो",
        "उधार चाहिए",
        # A QR code or a gift card (the founder's addition).
        "qr code bhejo",
        "QR bhej do",
        "qr scan karo",
        "qr code scan kar do",
        "क्यूआर कोड भेजो",
        "gift card bhejo",
        "gift card do",
        "gift card de do",
        "amazon gift card chahiye",
        "गिफ्ट कार्ड भेजो",
        "गिफ्ट कार्ड चाहिए",
    ],
)
def test_the_founders_money_asks_are_refused(text: str) -> None:
    assert filters.refusal(text) == "solicitation"


@pytest.mark.parametrize(
    "text",
    [
        # Abuse words' neighbours.
        "behen ki shaadi hai",
        "maa ke saath hoon",
        "maa ke log aaye",
        "chutti pe hoon",
        "gandi aadat hai",
        "gaana sun",
        "sharab haram hai",
        "लंडन जा रहा हूँ",
        # Left out on purpose (D-981): ordinary words, names, sentences.
        "mera kutta bahut cute hai",
        "kutti, Malayalam for child",
        "Kamini se milo",
        "mera sala aaya hai",
        "train chhoot gayi",
        "teri maa ki tabiyat kaisi hai",
        "300 BC",
        "the MC was great",
        "number do",
        # Money's neighbours.
        "paise ki tension mat lo",
        "maine bill ke paise bhar diye",
        "paise do baar kat gaye",  # the founder's: money cut twice
        "udhaar do baar liya",
        "udhaar dena accha nahi",
        "500 photos bheje",
        "recharge karna bhool gaya",
        "Bhim mera dost hai",
        "QR code se menu dekha",
        "usne mujhe birthday pe gift card diya",
        "पैसे की चिंता मत करो",
    ],
)
def test_the_founders_list_leaves_ordinary_sentences_alone(text: str) -> None:
    assert filters.refusal(text) is None


def test_a_nukta_matches_typed_either_way() -> None:
    """ "ड़" is one code point (U+095C) or "ड" and a nukta (U+0921 U+093C), as
    the keyboard sends it."""
    one = "भोस\u095cी"
    two = "भोस\u0921\u093cी"
    assert one != two
    assert filters.refusal(one) == filters.refusal(two) == "abuse"
