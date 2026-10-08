"""`GET /v1/search` (T-6.6, D-540): `@` and a username's start, exact first,
across India and past seeking, as a link reaches (D-493); or text, within the
radius, by name, username, city, intent or interest, among those the feed could
show. Either way only active accounts (D-500), never a hidden profile, nobody
blocked either way, and the badge as D-393 has it, never raw `is_verified`."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    FraudBand,
    Gender,
    OnboardingStep,
    Seeking,
    UserStatus,
)
from app.modules.discovery import rules
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.modules.discovery.support import (
    banded,
    bearer,
    block,
    error,
    north,
    person,
    photo,
    swipe,
)

pytestmark = pytest.mark.usefixtures("test_redis")

FIELDS = {
    "id",
    "first_name",
    "age",
    "username",
    "city",
    "main_photo_url",
    "shows_badge",
    "is_online",
    "exact",
}
# Bengaluru: about 1,900 km from Phagwara, far past any radius.
FAR = (12.97, 77.59)


async def _search(client: AsyncClient, token: str, q: str, **params: Any) -> Response:
    return await client.get(
        "/v1/search", params={"q": q, **params}, headers=bearer(token)
    )


async def _items(
    client: AsyncClient, token: str, q: str, **params: Any
) -> list[dict[str, Any]]:
    response = await _search(client, token, q, limit=50, **params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    for item in body["items"]:
        assert set(item) == FIELDS
    items: list[dict[str, Any]] = body["items"]
    return items


async def _names(client: AsyncClient, token: str, q: str) -> list[str]:
    return [item["username"] for item in await _items(client, token, q)]


def _url(key: str) -> str:
    return f"{make_test_settings().PUBLIC_CDN_URL}/{key}"


# --- @ search ---------------------------------------------------------------------


async def test_at_finds_the_exact_username_first_then_those_it_starts(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    for name in ("priya.k", "priya", "priyanka", "apriya", "pri_ya"):
        await person(db, make_user, at=north(1), username=name)

    items = await _items(client, token, "@priya")

    assert [i["username"] for i in items] == ["priya", "priya.k", "priyanka"]
    assert [i["exact"] for i in items] == [True, False, False]


async def test_at_ignores_case_and_spaces_around_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    await person(db, make_user, at=north(1), username="simran_k")

    items = await _items(client, token, "  @Simran_K ")

    assert [(i["username"], i["exact"]) for i in items] == [("simran_k", True)]


async def test_an_underscore_is_a_character_never_a_wildcard(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """`_` is LIKE's any-one-character: unescaped, `@a_b` would find `axb`."""
    _, token = await person(db, make_user, Gender.MALE)
    for name in ("a_bc", "axbc", "a.bc"):
        await person(db, make_user, at=north(1), username=name)

    assert await _names(client, token, "@a_b") == ["a_bc"]
    assert await _names(client, token, "@a.b") == ["a.bc"]


async def test_at_reaches_across_india_and_past_seeking(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-493: a username is a link, so it reaches whoever a link reaches."""
    _, token = await person(db, make_user, Gender.MALE, seeking=Seeking.WOMEN)
    await person(db, make_user, at=FAR, username="far_away")
    await person(db, make_user, Gender.MALE, at=north(1), username="far_man")

    assert await _names(client, token, "@far") == ["far_away", "far_man"]


async def test_at_shows_people_already_swiped(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), username="swiped_her")
    await swipe(db, me, her, "pass")

    assert await _names(client, token, "@swiped") == ["swiped_her"]


async def test_at_pages_without_repeating_or_skipping(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    names = ["pagey", *(f"pagey{n:02d}" for n in range(7))]
    for name in reversed(names):
        await person(db, make_user, at=north(1), username=name)

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = await _search(client, token, "@pagey", **params)
        assert response.status_code == 200, response.text
        body = response.json()
        seen += [item["username"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == names


# --- Text search ------------------------------------------------------------------


async def test_text_finds_names_near_and_alike(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    simran, _ = await person(db, make_user, at=north(1), first_name="Simran")
    simi, _ = await person(db, make_user, at=north(2), first_name="Simi")
    await person(db, make_user, at=north(3), first_name="Kavya")

    items = await _items(client, token, "simran")

    # Best match first; "Simi" by its prefix trigram, below the exact name.
    assert [i["id"] for i in items][:1] == [str(simran.id)]
    assert str(simi.id) in {i["id"] for i in items}
    assert "Kavya" not in {i["first_name"] for i in items}
    assert all(i["exact"] is False for i in items)


async def test_text_finds_by_username_and_by_city(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    by_name, _ = await person(db, make_user, at=north(1), username="chai_lover")
    in_city, _ = await person(db, make_user, at=north(2), city="Jalandhar")
    await person(db, make_user, at=north(3), city="Phagwara")

    assert [i["id"] for i in await _items(client, token, "chai_lov")] == [
        str(by_name.id)
    ]
    assert [i["id"] for i in await _items(client, token, "jalan")] == [str(in_city.id)]


async def test_text_finds_by_intent_and_interest_label(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The catalogues' labels (D-041, T-3.8): "serious" is in "Something
    serious"; "indie" in "Indie music"."""
    _, token = await person(db, make_user, Gender.MALE)
    serious, _ = await person(db, make_user, at=north(1), first_name="Asha")
    indie, _ = await person(db, make_user, at=north(2), first_name="Bina")
    neither, _ = await person(db, make_user, at=north(3), first_name="Chitra")
    for user in (serious, indie, neither):
        await db.execute(delete(ProfileIntent).where(ProfileIntent.user_id == user.id))
    db.add(ProfileIntent(user_id=serious.id, intent_id=1))
    db.add(ProfileIntent(user_id=indie.id, intent_id=5))
    db.add(ProfileIntent(user_id=neither.id, intent_id=5))
    db.add(ProfileInterest(user_id=indie.id, interest_id=3))
    await db.flush()
    want = {str(serious.id)}, {str(indie.id)}

    assert {i["id"] for i in await _items(client, token, "serious")} == want[0]
    assert {i["id"] for i in await _items(client, token, "INDIE")} == want[1]


async def test_text_keeps_to_the_radius_and_to_who_wants_whom(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Text search is discovery's: within the radius, mutual (D-540)."""
    _, token = await person(db, make_user, Gender.MALE, seeking=Seeking.WOMEN)
    near, _ = await person(db, make_user, at=north(1), first_name="Meera")
    await person(db, make_user, at=FAR, first_name="Meera")
    await person(db, make_user, Gender.MALE, at=north(1), first_name="Meera")
    await person(db, make_user, at=north(1), first_name="Meera", seeking=Seeking.WOMEN)

    assert [i["id"] for i in await _items(client, token, "Meera")] == [str(near.id)]


async def test_text_shows_people_already_swiped(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), first_name="Rhea")
    await swipe(db, me, her, "like")

    assert [i["id"] for i in await _items(client, token, "Rhea")] == [str(her.id)]


async def test_text_pages_without_repeating_or_skipping(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    for n in range(8):
        await person(db, make_user, at=north(1 + n % 3), city="Kapurthala")

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = await _search(client, token, "Kapur", **params)
        assert response.status_code == 200, response.text
        body = response.json()
        seen += [item["id"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == 8 == len(set(seen))


async def test_text_without_a_position_finds_nobody(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    await person(db, make_user, at=north(1), first_name="Tara")
    await _name(db, me, location=None)

    assert await _items(client, token, "Tara") == []


# --- What a row says ----------------------------------------------------------------


async def test_a_row_says_the_cards_fields_and_nothing_more(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(
        db,
        make_user,
        at=north(1),
        username="noor_s",
        first_name="Noor",
        city="Phagwara",
    )
    main = await photo(db, her, place=1, matched=True)
    await photo(db, her, place=3)
    her.is_verified = True
    await db.flush()

    (item,) = await _items(client, token, "@noor_s")

    assert item["id"] == str(her.id)
    assert (item["first_name"], item["city"]) == ("Noor", "Phagwara")
    assert isinstance(item["age"], int)
    assert item["main_photo_url"] == _url(f"p/{main.id}.jpg")
    assert item["shows_badge"] is True


async def test_the_badge_is_d393s_never_raw_is_verified(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """A matched selfie with no shown face that matched it is no badge."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), username="badge_no")
    await photo(db, her, place=0, matched=False)
    her.is_verified = True
    await db.flush()

    (item,) = await _items(client, token, "@badge_no")

    assert item["shows_badge"] is False


async def test_a_hidden_age_stays_hidden(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    await person(db, make_user, at=north(1), username="ageless", hide_age=True)

    (item,) = await _items(client, token, "@ageless")

    assert item["age"] is None


# --- Who is never found ------------------------------------------------------------


@pytest.mark.parametrize("q", ["@gone", "Gone"])
async def test_nobody_hidden_blocked_unfinished_or_held_back_is_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, q: str
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    hidden, _ = await person(db, make_user, at=north(1), is_hidden=True)
    blocked_by_me, _ = await person(db, make_user, at=north(1))
    blocked_me, _ = await person(db, make_user, at=north(1))
    unfinished, _ = await person(db, make_user, at=north(1))
    frozen, _ = await person(db, make_user, at=north(1))
    shadowed, _ = await person(db, make_user, at=north(1))
    found, _ = await person(db, make_user, at=north(1))
    gone = (hidden, blocked_by_me, blocked_me, unfinished, frozen, shadowed, found)
    for n, user in enumerate(gone):
        await _name(db, user, first_name="Gone", username=f"gone{n:02d}")
    await block(db, me, blocked_by_me)
    await block(db, blocked_me, me)
    unfinished.onboarding_step = OnboardingStep.SELFIE
    await banded(db, frozen, FraudBand.FREEZE)
    await banded(db, shadowed, FraudBand.SHADOW)
    # A match doesn't let a hidden profile into search (D-493).
    await _match(db, me, hidden)
    await db.flush()
    found_id = str(found.id)

    assert [i["id"] for i in await _items(client, token, q)] == [found_id]


@pytest.mark.parametrize("q", ["@still", "Still"])
@pytest.mark.parametrize(
    "status", [s for s in UserStatus if s is not UserStatus.ACTIVE]
)
async def test_only_active_accounts_are_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    q: str,
    status: UserStatus,
) -> None:
    """T-9.6, D-500: a deleted or paused account, or any not active, is found by
    nobody."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await _name(db, her, first_name="Still", username="still_here")
    her.status = status
    await db.flush()

    assert await _items(client, token, q) == []


async def test_the_shadowed_find_the_shadowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), username="shady_one")
    await banded(db, me, FraudBand.SHADOW)
    await banded(db, her, FraudBand.SHADOW)

    assert await _names(client, token, "@shady") == ["shady_one"]


async def test_you_never_find_yourself(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE, username="myself_m")

    assert await _items(client, token, "@myself") == []


# --- Refusals -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "q",
    [
        "",
        "   ",
        "x",
        "@",
        "@priya!",
        "@priya k",
        "@" + "a" * 21,
        "a" * (rules.SEARCH_MAX + 1),
    ],
)
async def test_a_query_it_cant_search_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, q: str
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await _search(client, token, q)

    assert response.status_code == 400, response.text
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert [f["field"] for f in error(response)["details"]["fields"]] == ["q"]


async def test_no_q_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await client.get("/v1/search", headers=bearer(token))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("q", ["@priya", "priya"])
async def test_a_cursor_from_the_other_mode_or_edited_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, q: str
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    other = [1.0, str(uuid.uuid4())] if q.startswith("@") else [True, "priya"]
    cursor = base64.urlsafe_b64encode(json.dumps(other).encode()).rstrip(b"=")

    response = await _search(client, token, q, cursor=cursor.decode())

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_search_is_limited_to_60_a_minute(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    for _ in range(60):
        assert (await _search(client, token, "@abc")).status_code == 200

    response = await _search(client, token, "@abc")

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


async def test_search_needs_sign_in_and_onboarding_done(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    assert (await client.get("/v1/search", params={"q": "@abc"})).status_code == 401
    unfinished, token = await person(db, make_user, Gender.MALE)
    unfinished.onboarding_step = OnboardingStep.PHOTOS
    await db.flush()

    response = await _search(client, token, "@abc")

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


# --- Helpers --------------------------------------------------------------------------


async def _name(db: AsyncSession, user: User, **profile: Any) -> None:
    row = await db.get(Profile, user.id)
    assert row is not None
    for column, value in profile.items():
        setattr(row, column, value)
    await db.flush()


async def _match(db: AsyncSession, a: User, b: User) -> None:
    low, high = (a.id, b.id) if a.id.bytes < b.id.bytes else (b.id, a.id)
    await db.execute(
        text("INSERT INTO matches (id, user_low, user_high) VALUES (:id, :l, :h)"),
        {"id": uuid.uuid4(), "l": low, "h": high},
    )
