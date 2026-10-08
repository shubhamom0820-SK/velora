"""The `Card` (T-6.2): exactly its fields, never a date of birth, a position
or raw `is_verified`; the age and distance unless hidden, the distance in
whole kilometres between grid points, never under 1 (D-034, D-490); the main
photo the lowest approved public place or null (P-75, D-392); the badge D-393's
rule; online and new by the server's clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, PhotoKind, ReviewStatus
from app.modules.profiles.models import Profile, ProfileIntent
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.modules.discovery.support import discover, north, person, photo

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)

FIELDS = {
    "id",
    "first_name",
    "age",
    "username",
    "city",
    "hometown",
    "distance_km",
    "intent_ids",
    "bio_line",
    "main_photo_url",
    "shows_badge",
    "is_online",
    "is_new",
}


async def _card(client: AsyncClient, token: str, user: User) -> dict[str, Any]:
    response = await discover(client, token, limit=50)
    assert response.status_code == 200, response.text
    [card] = [c for c in response.json()["items"] if c["id"] == str(user.id)]
    assert set(card) == FIELDS
    return dict(card)


def _url(key: str) -> str:
    return f"{make_test_settings().PUBLIC_CDN_URL}/{key}"


async def test_a_card_says_exactly_this(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    about = "Filter coffee at dawn, ghazals at dusk; " * 5
    her, _ = await person(
        db,
        make_user,
        at=north(3),
        first_name="Simran",
        city="Phagwara",
        hometown="Ludhiana",
        about=about[:300],
        last_active_at=NOON - timedelta(minutes=2),
        created_at=NOON - timedelta(days=20),
    )
    for intent_id in (7, 2):
        db.add(ProfileIntent(user_id=her.id, intent_id=intent_id))
    shown = await photo(db, her, place=0, matched=True)

    profile = await db.get(Profile, her.id)
    assert profile is not None and profile.username is not None
    username = profile.username

    card = await _card(client, token, her)

    assert card == {
        "id": str(her.id),
        "first_name": "Simran",
        "age": 25,
        "username": username,
        "city": "Phagwara",
        "hometown": "Ludhiana",
        "distance_km": 3,
        "intent_ids": [2, 7],
        "bio_line": about[:90],
        "main_photo_url": _url(f"p/{shown.id}.jpg"),
        "shows_badge": True,
        "is_online": True,
        "is_new": False,
    }
    assert len(card["bio_line"]) == 90


async def test_hidden_age_and_distance_are_null(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(3), hide_age=True, hide_distance=True)

    card = await _card(client, token, her)

    assert (card["age"], card["distance_km"]) == (None, None)


@pytest.mark.parametrize(("steps", "km"), [(0, 1), (0.4, 1), (2, 2), (5, 6), (9, 10)])
async def test_the_distance_is_whole_kilometres_between_grid_points_never_under_1(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, steps: float, km: int
) -> None:
    """0.4 of a step is inside the same cell: the same grid point, 1 km.
    One step is 1.11 km, so 5 are 5.56 (6) and 9 are 10.0."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(steps))

    assert (await _card(client, token, her))["distance_km"] == km


async def test_the_main_photo_is_the_lowest_approved_public_place_gap_or_not(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """P-75 (8 October 2026): the server never moves a photo up, so the main
    one is the lowest place approved, 0 or not. Nothing private, pending,
    rejected, no selfie and no face photo, ever comes before it."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await photo(db, her, place=0, status=ReviewStatus.REJECTED)
    await photo(db, her, place=1, status=ReviewStatus.PENDING)
    await photo(db, her, kind=PhotoKind.PRIVATE)
    await photo(db, her, kind=PhotoKind.VERIFICATION)
    await photo(db, her, kind=PhotoKind.SELFIE)
    main = await photo(db, her, place=3)
    await photo(db, her, place=4)

    card = await _card(client, token, her)

    assert card["main_photo_url"] == _url(f"p/{main.id}.jpg")


async def test_no_approved_public_photo_is_a_null_main_photo(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-392: the web draws a grey silhouette with the name."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await photo(db, her, kind=PhotoKind.VERIFICATION)
    await photo(db, her, place=0, status=ReviewStatus.PENDING)

    card = await _card(client, token, her)

    assert card["main_photo_url"] is None


@pytest.mark.parametrize(
    ("verified", "matched", "badge"),
    [
        (True, True, True),
        (True, False, False),
        (True, None, False),
        (False, True, False),
    ],
)
async def test_the_badge_is_d393s_never_is_verified_alone(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    verified: bool,
    matched: bool | None,
    badge: bool,
) -> None:
    """A man, so `is_verified` can be either (D-008): matched selfie and a
    shown face that matched it, or no badge."""
    _, token = await person(db, make_user)
    him, _ = await person(db, make_user, Gender.MALE, at=north(1), verified=verified)
    await photo(db, him, matched=matched)

    assert (await _card(client, token, him))["shows_badge"] is badge


async def test_a_match_on_a_photo_no_longer_shown_is_no_badge(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await photo(db, her, place=0, status=ReviewStatus.REJECTED, matched=True)
    await photo(db, her, place=1, matched=False)

    assert (await _card(client, token, her))["shows_badge"] is False


@pytest.mark.parametrize(
    ("ago", "online"),
    [
        (timedelta(0), True),
        (timedelta(minutes=5), True),
        (timedelta(minutes=5, seconds=1), False),
        (None, False),
    ],
)
async def test_online_is_active_in_the_last_five_minutes(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    ago: timedelta | None,
    online: bool,
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(
        db, make_user, at=north(1), last_active_at=None if ago is None else NOON - ago
    )

    assert (await _card(client, token, her))["is_online"] is online


@pytest.mark.parametrize(
    ("ago", "new"),
    [
        (timedelta(days=6, hours=23), True),
        (timedelta(days=7), True),
        (timedelta(days=7, seconds=1), False),
    ],
)
async def test_new_is_joined_in_the_last_seven_days(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    ago: timedelta,
    new: bool,
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), created_at=NOON - ago)

    assert (await _card(client, token, her))["is_new"] is new


async def test_a_short_about_is_the_whole_bio_line(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    about = "Forty characters of about, just enough."
    her, _ = await person(db, make_user, at=north(1), about=about + ".")

    assert (await _card(client, token, her))["bio_line"] == about + "."
