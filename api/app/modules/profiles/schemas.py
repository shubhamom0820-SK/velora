"""Profile requests and responses (04-API.md, Me & onboarding)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.enums import Seeking

# `intents.id` is a smallint: an id past its range would otherwise reach the
# database and fail there, a 500 for what is only a bad request.
IntentId = Annotated[int, Field(ge=1, le=32767)]


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


class ProfilePatch(BaseModel):
    """Any of the four, each only if sent (a null is not sent). First name,
    hometown and city are the `profile` step's; about is the `about` step's
    (D-068). The rules are `profiles.rules`, checked by the service."""

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
