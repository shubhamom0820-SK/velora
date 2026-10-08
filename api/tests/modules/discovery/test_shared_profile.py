"""`GET /v1/public-profiles/{username}` (T-6.8, D-544): what `/@username`
shows someone not signed in. Only when its owner turned the public link on;
off for everyone until then. Then only what the page shows; every other case
the one `NOT_FOUND`; no view recorded; 60 a minute per address."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FraudBand, Gender, OnboardingStep, UserStatus
from app.modules.discovery.models import ProfileView
from tests.conftest import MakeUser, make_test_settings
from tests.modules.discovery.support import banded, bearer, north, person, photo

pytestmark = pytest.mark.usefixtures("test_redis")

NOBODY = {"error": {"code": "NOT_FOUND", "message": "Not found."}}
FIELDS = {"username", "first_name", "age", "city", "main_photo_url"}


async def _get(client: AsyncClient, username: str, **headers: str) -> Response:
    return await client.get(f"/v1/public-profiles/{username}", headers=headers)


async def _refused(client: AsyncClient, username: str) -> None:
    response = await _get(client, username)
    assert (response.status_code, response.json()) == (404, NOBODY)


async def _public(client: AsyncClient, username: str) -> dict[str, Any]:
    response = await _get(client, username)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == FIELDS
    return body


async def test_a_fresh_account_is_not_found_until_she_turns_the_link_on(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The founder's rule (D-544): her photo, name, age and city reach the
    open internet only when she chooses."""
    _, token = await person(db, make_user, username="noor_s", first_name="Noor")

    await _refused(client, "noor_s")

    turned_on = await client.patch(
        "/v1/me/settings", json={"public_link": True}, headers=bearer(token)
    )
    assert turned_on.status_code == 200, turned_on.text
    assert turned_on.json()["profile"]["public_link"] is True
    assert (await _public(client, "noor_s"))["first_name"] == "Noor"

    await client.patch(
        "/v1/me/settings", json={"public_link": False}, headers=bearer(token)
    )
    await _refused(client, "noor_s")


async def test_it_shows_the_page_and_nothing_more(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    her, _ = await person(
        db,
        make_user,
        username="simran.k",
        first_name="Simran",
        city="Phagwara",
        public_link=True,
    )
    main = await photo(db, her, place=1, matched=True)
    await photo(db, her, place=3)
    her.is_verified = True
    await db.flush()
    her_id = str(her.id)

    response = await _get(client, "Simran.K")

    body = response.json()
    assert body == {
        "username": "simran.k",
        "first_name": "Simran",
        "age": body["age"],
        "city": "Phagwara",
        "main_photo_url": f"{make_test_settings().PUBLIC_CDN_URL}/p/{main.id}.jpg",
    }
    assert isinstance(body["age"], int)
    # No id, no badge, nothing else of hers.
    assert her_id not in response.text
    assert "badge" not in response.text and "verified" not in response.text


async def test_a_hidden_age_and_no_photo(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await person(db, make_user, username="ageless", hide_age=True, public_link=True)

    body = await _public(client, "ageless")

    assert (body["age"], body["main_photo_url"]) == (None, None)


async def test_every_refusal_is_the_same_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await person(db, make_user, username="r_hidden", is_hidden=True, public_link=True)
    unfinished, _ = await person(
        db, make_user, username="r_unfinished", public_link=True
    )
    frozen, _ = await person(db, make_user, username="r_frozen", public_link=True)
    shadowed, _ = await person(db, make_user, username="r_shadowed", public_link=True)
    unfinished.onboarding_step = OnboardingStep.SELFIE
    await banded(db, frozen, FraudBand.FREEZE)
    await banded(db, shadowed, FraudBand.SHADOW)
    await db.flush()

    for name in (
        "r_hidden",
        "r_unfinished",
        "r_frozen",
        "r_shadowed",
        "nobody_here",
        "no",
        "bad!name",
        "%25",
    ):
        await _refused(client, name)


@pytest.mark.parametrize(
    "status", [s for s in UserStatus if s is not UserStatus.ACTIVE]
)
async def test_an_account_not_active_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: UserStatus
) -> None:
    her, _ = await person(db, make_user, username="paused_one", public_link=True)
    her.status = status
    await db.flush()

    await _refused(client, "paused_one")


async def test_signed_in_or_not_it_records_no_view(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    await person(db, make_user, at=north(1), username="viewed_not", public_link=True)

    await _public(client, "viewed_not")
    await _get(client, "viewed_not", Authorization=f"Bearer {token}")

    assert await db.scalar(select(func.count()).select_from(ProfileView)) == 0


async def test_it_is_limited_to_60_a_minute_per_address(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await person(db, make_user, username="popular", public_link=True)
    for _ in range(60):
        assert (await _get(client, "popular")).status_code == 200

    response = await _get(client, "popular")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
