"""Profile requests and responses (04-API.md, Me & onboarding)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

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
