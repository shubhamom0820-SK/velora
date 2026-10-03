"""What a profile's text may be (T-3.7): pure functions, shared by the service
and the dev seed, so seeded profiles are held to the rules people are.

Each `*_problem` returns None for a good value, or the problem, worded for
`details.fields[].problem`. Values are checked as `clean_text` leaves them:
trimmed and in NFC, the form they're stored in.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.config import APP_NAME

FIRST_NAME_MAX = 30
PLACE_MAX = 40
ABOUT_MIN, ABOUT_MAX = 40, 300


def clean_text(value: str) -> str:
    """Trimmed and in NFC: one way to write each character, so a name typed
    on two keyboards is stored, counted and compared the same."""
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n")).strip()


# --- First name: letters in any script ------------------------------------------

# Inside a name only: O'Brien, D’Souza (a phone's keyboard types ’), Mary-Jane.
_JOINS = re.compile(r"['’-]")


def first_name_problem(name: str) -> str | None:
    """1 to 30 characters; words of letters, in any script, one space apart;
    an apostrophe or hyphen only between letters. A letter may carry marks,
    the vowel signs and viramas that Devanagari, Gurmukhi and every other
    Indic script write names with."""
    if not 1 <= len(name) <= FIRST_NAME_MAX:
        return f"must be 1 to {FIRST_NAME_MAX} characters"
    for word in name.split(" "):
        if not word:
            return "has two spaces in a row"
        if not all(_is_letters(part) for part in _JOINS.split(word)):
            return (
                "may only hold letters, single spaces, and an apostrophe or hyphen "
                "inside a name"
            )
    return None


def _is_letters(part: str) -> bool:
    """A letter, then letters and marks: never empty, never a mark first."""
    if not part or not _category(part[0]).startswith("L"):
        return False
    return all(_category(c)[0] in "LM" for c in part[1:])


def _category(char: str) -> str:
    return unicodedata.category(char)


# --- Hometown and city --------------------------------------------------------------


def place_problem(place: str) -> str | None:
    if not 1 <= len(place) <= PLACE_MAX:
        return f"must be 1 to {PLACE_MAX} characters"
    if _has_control(place, allow_newline=False):
        return "can't hold control characters"
    return None


def _has_control(text: str, *, allow_newline: bool) -> bool:
    """Controls, format characters, unassigned code points and the rest of
    Unicode's C categories. A NUL would fail at the database; the rest make
    text that renders as something other than what it holds."""
    return any(
        _category(c).startswith("C") and not (allow_newline and c == "\n") for c in text
    )


# --- About: no links, no phone numbers ------------------------------------------

# A scheme, `www.`, or a bare domain: a name, a dot and one of the endings
# people actually type for a link, India's and the link shorteners' included
# (bit.ly, wa.me, t.me, youtu.be, linktr.ee). Two limits keep ordinary writing
# out: the ending in lowercase, since a capital after a missed space starts a
# sentence ("chai.In the evenings"); and a name of two characters or more,
# since "B.Com" and "B.Tech" are degrees, unless a path follows ("x.com/ravi").
# T-7.3's contact masking in chat is broader, and separate.
_TLDS = (
    "com|in|net|org|io|app|co|me|ly|gg|xyz|info|biz|ai|dev|be|ee|gl|cc|tv|to|"
    "us|uk|link|page|site|online|store|shop|live|club"
)
_URL = re.compile(
    rf"(?i:[a-z][a-z0-9+.-]*://|\bwww\.)"
    rf"|\b[\w-]{{2,}}\.(?:{_TLDS})\b"
    rf"|\b\w\.(?:{_TLDS})/"
)
# A run of digits with single separators between them: space, dash or dot.
_DIGIT_RUN = re.compile(r"\d(?:[ .-]?\d)*")
_SEPARATOR = re.compile(r"[ .-]")
# The Indian mobile number this exists to catch is ten digits (D-068's
# answers); a run of fewer is a date, a year or a range of them.
PHONE_DIGITS = 10
PHONE_SEPARATORS = 2


def has_phone_number(text: str) -> bool:
    """Whether `text` holds a run of 10 or more digits with at most two
    separators inside it: "98765 43210" and "+91 98765 43210" do; "2010-2015"
    and digits scattered across a sentence don't. Any script's digits count."""
    for run in _DIGIT_RUN.findall(text):
        groups = [len(group) for group in _SEPARATOR.split(run)]
        # At most two separators: any three groups side by side, or fewer.
        window = PHONE_SEPARATORS + 1
        for start in range(len(groups)):
            if sum(groups[start : start + window]) >= PHONE_DIGITS:
                return True
    return False


def about_problem(about: str) -> str | None:
    if not ABOUT_MIN <= len(about) <= ABOUT_MAX:
        return f"must be {ABOUT_MIN} to {ABOUT_MAX} characters"
    if _has_control(about, allow_newline=True):
        return "can't hold control characters"
    if _URL.search(about):
        return "can't hold a link"
    if has_phone_number(about):
        return "can't hold a phone number"
    return None


# --- Usernames --------------------------------------------------------------------

USERNAME = re.compile(r"[a-z0-9._]{4,20}")
USERNAME_MAX = 20

# Names that impersonate the staff or the product (D-068). Not route segments:
# usernames live under D-001's `/@`, never a bare path. Matched with case, dots
# and underscores ignored, so `ad.min` and `Ad_Min` are admin. Short ones stay
# listed though the format refuses them, since a dotted variant (`a.p.i`) is
# long enough to pass it.
RESERVED_USERNAMES = frozenset(
    {
        "admin",
        "administrator",
        "mod",
        "moderator",
        "support",
        "help",
        "helpdesk",
        "staff",
        "team",
        "official",
        "root",
        "system",
        "security",
        "api",
        "www",
        "mail",
        "billing",
        "payments",
        "legal",
        "privacy",
        "terms",
        "grievance",
        "knot",
        "knots",
        "thread",
        "threads",
        "vela",
        "velas",
        "me",
        "null",
        "undefined",
    }
)


def _skeleton(name: str) -> str:
    return re.sub(r"[._]", "", name.lower())


def _brand() -> str:
    """The brand as a username would spell it, so a rename moves it (rule 17)."""
    return re.sub(r"[^a-z0-9]", "", APP_NAME.lower())


def username_problem(username: str) -> str | None:
    """The format alone (03-SCHEMA): what `username` must look like, in the
    lowercase it is stored in."""
    if not USERNAME.fullmatch(username):
        return "must be 4 to 20 of a-z, 0-9, '.' and '_'"
    return None


def is_reserved(username: str) -> bool:
    skeleton = _skeleton(username)
    return skeleton in {_skeleton(name) for name in RESERVED_USERNAMES} or (
        skeleton == _brand()
    )
