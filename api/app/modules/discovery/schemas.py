"""`GET /v1/discover` (T-6.2) and `GET /v1/users/{id}` (T-6.3): the feed, its
cards, and a public profile (04-API.md)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import ThreadStatus
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


class KudosCounts(BaseModel):
    """How many people gave each of the four kudos (T-8.x builds the giving)."""

    great_conversation: int
    genuinely_funny: int
    easy_to_talk_to: int
    really_thoughtful: int


class ThreadWithMe(BaseModel):
    """The Thread between the viewer and this person, if there is one: its
    state, and when it expires while it is active (never once knotted)."""

    id: UUID
    status: ThreadStatus
    expires_at: datetime | None


class PublicProfile(Card):
    """A `Card` and the rest of the profile (T-6.3): the whole `about`, every
    approved public photo in place order (the first is `main_photo_url`),
    the interests, the kudos unless they hide them, how many private photos
    they hold (never one of them), and what is already between the viewer and
    them. Never a position, a date of birth or raw `is_verified`."""

    about: str
    photo_urls: list[str]
    interest_ids: list[int]
    # Null when they hide their kudos (`show_kudos`).
    kudos: KudosCounts | None
    album_photo_count: int
    match_id: UUID | None
    thread: ThreadWithMe | None
