"""Discovery's rules (T-6.2): who may be shown to whom, how a feed is ranked,
and what a `Card` says. No I/O: the repository holds the SQL that applies them,
the service reads and calls these.

The ranking is D-032's four terms with D-491's weights. Each term is 0 to 1, so
a score is 0 to 1, and the `new` feed adds 1 for anyone who joined within
`NEW_FOR`, which puts every new face first without changing how they rank
among themselves:

    score = 0.40 · D + 0.30 · R + 0.15 · V + 0.15 · C

- D, distance: 1 / (1 + km / 5), between grid points (D-490): 1 at the same
  point, 0.5 at 5 km, about 0.17 at 25 km.
- R, recency: 1 / (1 + hours since last active / 24): 0.5 a day ago; 0 for
  someone never active.
- V, `is_verified`: the selfie matched (D-032 unchanged, P-290). The ranking
  is not a claim; the badge is D-393's, and stricter.
- C, completeness / 100: 0.5 to 1.0 (D-310, kept current by P-210).

Every term is measured at the feed's `as_of`, the instant its first page was
ranked, which each cursor carries, so a scroll is one ranking: a card on page 1
can't fall to page 2 because time passed between them (D-491). Every candidate
is scored; a window of the nearest few was built and measured, and saved
nothing (D-495).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from app.core.enums import Gender, Seeking

WEIGHT_DISTANCE: Final = 0.40
WEIGHT_RECENCY: Final = 0.30
WEIGHT_VERIFIED: Final = 0.15
WEIGHT_COMPLETENESS: Final = 0.15
# D: the distance at which the term halves.
DISTANCE_HALF_KM: Final = 5.0
# R: the time since last active at which the term halves.
RECENCY_HALF: Final = timedelta(hours=24)
# The `new` feed's lift: more than any score, so the new come first.
NEW_LIFT: Final = 1.0

# A `Card`'s `is_online`, and the `online` feed (T-6.2).
ONLINE_FOR: Final = timedelta(minutes=5)
# A `Card`'s `is_new`, and the `new` feed: joined this recently.
NEW_FOR: Final = timedelta(days=7)
# A `Card`'s `bio_line`: the first this many characters of `about`.
BIO_LINE_CHARS: Final = 90

# Who each `seeking` wants to see.
WANTS: Final[dict[Seeking, frozenset[Gender]]] = {
    Seeking.WOMEN: frozenset({Gender.FEMALE}),
    Seeking.MEN: frozenset({Gender.MALE}),
    Seeking.EVERYONE: frozenset({Gender.FEMALE, Gender.MALE}),
}


def wanted_genders(seeking: Seeking | None) -> frozenset[Gender]:
    """The genders someone seeking `seeking` is shown: none before they say."""
    return WANTS.get(seeking, frozenset()) if seeking is not None else frozenset()


def seekings_wanting(gender: Gender | None) -> frozenset[Seeking]:
    """Every `seeking` that wants to see someone of `gender`: the other half
    of the match, since discovery is mutual."""
    if gender is None:
        return frozenset()
    return frozenset(seeking for seeking, genders in WANTS.items() if gender in genders)


def distance_km(metres: float) -> int:
    """D-034: whole kilometres, never under 1. Half rounds up, as people
    read it, never to even."""
    return max(1, math.floor(metres / 1000 + 0.5))


def bio_line(about: str | None) -> str:
    return (about or "")[:BIO_LINE_CHARS]


# --- Search (T-6.6, D-540) -----------------------------------------------------------

# `q`, whole, `@` included.
SEARCH_MAX: Final = 50
# Text mode needs this many characters: one letter matches nearly everyone.
SEARCH_TEXT_MIN: Final = 2
# pg_trgm's `%`, set for the search's own transaction rather than left to the
# database's default: a name matches at this similarity or more.
SIMILARITY: Final = 0.3
# After the `@`: what a username may hold (P-59), any case, 1 to 20 of them;
# a prefix of one is the search.
USERNAME_PREFIX: Final = re.compile(r"[A-Za-z0-9._]{1,20}")


@dataclass(frozen=True)
class Query:
    """What `q` asks: `@` and a username's start, or text."""

    username: bool
    term: str


def parse_query(q: str) -> Query | str:
    """The search `q` asks for, or what is wrong with it."""
    q = q.strip()
    if q.startswith("@"):
        term = q[1:]
        if not USERNAME_PREFIX.fullmatch(term):
            return "after @, 1 to 20 of a-z, 0-9, . and _"
        return Query(username=True, term=term.lower())
    if len(q) < SEARCH_TEXT_MIN:
        return f"at least {SEARCH_TEXT_MIN} characters"
    return Query(username=False, term=q)


def like_prefix(term: str) -> str:
    """`term` as a LIKE pattern matching what starts with it: its `\\`, `%` and
    `_` escaped, so `@a_b` never finds `axb` (D-540)."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def like_contains(term: str) -> str:
    """`term` as a LIKE pattern matching what holds it anywhere, escaped."""
    return f"%{like_prefix(term)}"
