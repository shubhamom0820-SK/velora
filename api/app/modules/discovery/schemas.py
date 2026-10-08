"""`GET /v1/discover` (T-6.2), `GET /v1/users/{id}` (T-6.3) and search
(T-6.6): the feed, its cards, a public profile and search's rows (04-API.md)."""

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
    """`Page<Card>`: by score, best first, then by id (D-491); and how many of
    today's swipes a man has left, so the deck can say it before his first
    swipe (T-6.5): the same number `POST /swipes` returns, null for anyone
    uncapped, a woman."""

    swipes_left: int | None = None


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


class SearchResult(BaseModel):
    """One person in search's results (T-6.6, D-540): a row, not a card. The
    `Card`'s rules for each field it shares; never a distance, a date of
    birth, a position or raw `is_verified`."""

    id: UUID
    first_name: str
    # Null when they hide it.
    age: int | None
    username: str
    city: str | None
    # As the `Card`'s: the approved public photo at the lowest place, or null.
    main_photo_url: str | None
    # D-393's badge, as the `Card`'s.
    shows_badge: bool
    is_online: bool
    # `@` search only: the username is exactly what was asked.
    exact: bool


class SearchResultPage(Page[SearchResult]):
    """`Page<SearchResult>`: `@` search's exact match first, then usernames in
    order; text search's best name match first, then by id (D-540)."""


class SharedProfile(BaseModel):
    """`/@username` for someone not signed in (T-6.8, D-544): only what the
    page shows, and only when its owner turned their public link on. Never an
    id, a badge, a distance, the about, or any other photo."""

    username: str
    first_name: str
    # Null when they hide it.
    age: int | None
    city: str | None
    # As the `Card`'s (D-494), or null.
    main_photo_url: str | None
