"""`GET /v1/discover` — the request's feed and the response (04-API.md, T-6.2)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.core.pagination import Page


class Feed(StrEnum):
    # Ranked by D-491's score.
    FORYOU = "foryou"
    # Joined within 7 days first, then the rest, each by score.
    NEW = "new"
    # Active within 5 minutes only, by score.
    ONLINE = "online"


class Card(BaseModel):
    """One person in a feed. Never a date of birth, a position, a phone number
    or raw `is_verified`: an age, a distance in whole kilometres between grid
    points (D-034, D-490), and the badge as D-393 has it."""

    id: UUID
    first_name: str
    # Null when they hide it.
    age: int | None
    username: str
    city: str | None
    hometown: str | None
    # Whole kilometres, at least 1; null when they hide it.
    distance_km: int | None
    intent_ids: list[int]
    # The first 90 characters of `about`.
    bio_line: str
    # Their approved public photo at the lowest place; null with none, and the
    # web shows a grey silhouette with the name (D-392).
    main_photo_url: str | None
    # D-393: the selfie matched the face photo and a shown face matched the
    # selfie. Never "verified" in copy (D-262).
    shows_badge: bool
    # Active within the last 5 minutes.
    is_online: bool
    # Joined within the last 7 days.
    is_new: bool


class CardPage(Page[Card]):
    """`Page<Card>`: by score, best first, then by id (D-491)."""
