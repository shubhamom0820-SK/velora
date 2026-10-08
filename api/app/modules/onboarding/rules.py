"""What finishing onboarding asks (T-4.8, D-310): what a profile must hold to
go from `selfie` to `done`, who may finish without a matched selfie, who may
leave the `photos` step without a face photo (T-4.12, D-391), and the
profile's completeness. No I/O: the service reads, these decide, and the dev
seed holds its finished profiles to the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.core.enums import Gender, Seeking
from app.modules.profiles.service import INTERESTS_PER_PROFILE

# Each thing a finished profile needs that this one lacks: `PROFILE_INCOMPLETE`'s
# `details.missing`, in the order onboarding asks for them, so the first is the
# earliest screen to go back to. No photo is among them (D-392, T-4.12): nobody
# needs a public photo, men included.
Missing = Literal[
    "seeking",
    "intents",
    "first_name",
    "hometown",
    "city",
    "location",
    "username",
    "about",
    "interests",
]

# D-041: 1 to 3 intents, as `PUT /me/seeking` takes them.
INTENTS_MIN, INTENTS_MAX = 1, 3

# Who may finish without a selfie that matched their photos: men only (D-008).
# An allowlist, as the web's "Skip for now" is: anyone else, a woman or someone
# with no gender at all, needs the match. `users_done_needs_a_match` holds the
# database to the same rule.
MAY_FINISH_UNMATCHED: Final = frozenset({Gender.MALE})

# Who may leave the `photos` step with no face photo: men only (D-391, D-008:
# the selfie is optional for them, so the photo it is compared with is too).
# An allowlist, as above: anyone else, a woman or someone with no gender, needs
# one, pending or approved. The server's rule, not the screen's.
MAY_LEAVE_PHOTOS_WITHOUT_A_FACE_PHOTO: Final = frozenset({Gender.MALE})

# Completeness (D-310): every finished profile meets the requirements, so they
# count 50; each approved public photo after the first adds 10, the five more
# places there are, to 100. What varies between finished profiles is how many
# photos they show, and discovery ranks by it a little (D-032).
COMPLETENESS_BASE: Final = 50
COMPLETENESS_PER_PHOTO: Final = 10
COMPLETENESS_MAX: Final = 100


@dataclass(frozen=True)
class Facts:
    """What the requirements read from a profile."""

    seeking: Seeking | None
    intents: int
    first_name: str | None
    hometown: str | None
    city: str | None
    located: bool
    username: str | None
    about: str | None
    # Approved public photos only: discovery shows nothing else (D-310).
    approved_photos: int
    interests: int


def missing(facts: Facts) -> list[Missing]:
    """Every requirement `facts` doesn't meet, in onboarding's order; none,
    and the profile may finish."""
    met: dict[Missing, bool] = {
        "seeking": facts.seeking is not None,
        "intents": INTENTS_MIN <= facts.intents <= INTENTS_MAX,
        "first_name": bool(facts.first_name),
        "hometown": bool(facts.hometown),
        "city": bool(facts.city),
        "location": facts.located,
        "username": bool(facts.username),
        "about": bool(facts.about),
        "interests": facts.interests == INTERESTS_PER_PROFILE,
    }
    return [requirement for requirement, ok in met.items() if not ok]


def needs_a_match(gender: Gender | None) -> bool:
    """Whether finishing needs a selfie that matched the face photo."""
    return gender not in MAY_FINISH_UNMATCHED


def needs_a_face_photo(gender: Gender | None) -> bool:
    """Whether leaving the `photos` step needs a face photo, pending or
    approved (T-4.12)."""
    return gender not in MAY_LEAVE_PHOTOS_WITHOUT_A_FACE_PHOTO


def completeness(approved_photos: int) -> int:
    """A finished profile's completeness, 50 to 100, from its approved public
    photos: 50 at none, the same as at one, so a profile that shows nothing
    sits at the bottom of discovery's ranking (D-392, D-032), on purpose."""
    extra = max(0, approved_photos - 1)
    return min(COMPLETENESS_MAX, COMPLETENESS_BASE + COMPLETENESS_PER_PHOTO * extra)
