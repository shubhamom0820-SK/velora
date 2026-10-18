"""Profile requests and responses (04-API.md, Me & onboarding)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Discriminator, Field, StringConstraints, Tag

from app.core.enums import Seeking

# `intents.id` and `interests.id` are smallints: an id past their range would
# otherwise reach the database and fail there, a 500 for a bad request.
IntentId = Annotated[int, Field(ge=1, le=32767)]
InterestId = IntentId


class Intent(BaseModel):
    """One of the catalogue's intents (D-041). The web shows its own label for
    each id, from `en.ts` (P-26)."""

    id: int
    slug: str
    label: str


class SeekingSet(BaseModel):
    seeking: Seeking
    # 1 to 3, all different (D-041); the service checks they're all different
    # and all in the catalogue.
    intent_ids: Annotated[list[IntentId], Field(min_length=1, max_length=3)]


class Interest(BaseModel):
    """One of the catalogue's interests (T-1.14). Every row has a slug and a
    label, though the columns allow NULL until P-24."""

    id: int
    slug: str
    label: str


class InterestsSet(BaseModel):
    # Exactly 5 (03-SCHEMA); the service checks they're all different and all
    # in the catalogue.
    interest_ids: Annotated[list[InterestId], Field(min_length=5, max_length=5)]


class ProfilePatch(BaseModel):
    """Any of the four, each only if sent (a null is not sent). First name,
    hometown and city are the `profile` step's; about is the `about` step's
    (D-068). An about that is empty once trimmed means none: at the about step
    it skips the bio, after it clears it (D-951). The rules are
    `profiles.rules`, checked by the service."""

    # The rules measure the text trimmed; these caps only stop a body far past
    # any rule before it is read.
    first_name: Annotated[str, StringConstraints(max_length=120)] | None = None
    hometown: Annotated[str, StringConstraints(max_length=160)] | None = None
    city: Annotated[str, StringConstraints(max_length=160)] | None = None
    about: Annotated[str, StringConstraints(max_length=1200)] | None = None


class UsernameSet(BaseModel):
    # Typed in any case; stored in lowercase (D-068).
    username: Annotated[str, StringConstraints(max_length=64)]


class UsernameAvailability(BaseModel):
    available: bool
    # Offered when a name is taken: the name and two digits, checked free.
    suggestion: str | None = None


class Area(BaseModel):
    """One of the seeded areas, for the picker (T-4.10). Never its centroid:
    the picker shows names, and data no screen shows isn't sent."""

    id: UUID
    city: str
    name: str


class PositionSet(BaseModel):
    """A position the browser read. The schema takes any point on Earth; the
    service requires one inside India (D-220), a rule beyond the schema
    (D-082)."""

    model_config = ConfigDict(extra="forbid")

    lat: Annotated[float, Field(strict=True, ge=-90, le=90, allow_inf_nan=False)]
    lng: Annotated[float, Field(strict=True, ge=-180, le=180, allow_inf_nan=False)]


class AreaSet(BaseModel):
    """An area picked from `GET /areas`, when no position is shared."""

    model_config = ConfigDict(extra="forbid")

    area_id: UUID


def _location_form(body: object) -> str:
    """Which of the two a body is trying to be: an area if it names one,
    else a position. Checked against that one alone, so a refusal names only
    its own fields, as `position.lng` or `area.area_id`."""
    return "area" if isinstance(body, dict) and "area_id" in body else "position"


LocationSet = Annotated[
    Annotated[PositionSet, Tag("position")] | Annotated[AreaSet, Tag("area")],
    Discriminator(_location_form),
]
