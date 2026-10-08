"""`GET /v1/users/by-username/{u}` (T-6.6): the profile a username names, in
any case, under exactly `GET /users/{id}`'s rule (D-493); active accounts only
(D-500); every refusal, a name nobody holds and an erased one's among them
(D-505), the same `NOT_FOUND`."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FraudBand, Gender, Seeking, UserStatus
from app.modules.discovery.models import ProfileView
from app.modules.profiles.models import Profile
from tests.conftest import MakeUser
from tests.modules.discovery.support import banded, bearer, block, north, person

pytestmark = pytest.mark.usefixtures("test_redis")

NOBODY = {"error": {"code": "NOT_FOUND", "message": "Not found."}}


async def _get(client: AsyncClient, token: str, username: str) -> Response:
    return await client.get(f"/v1/users/by-username/{username}", headers=bearer(token))


async def _ok(client: AsyncClient, token: str, username: str) -> dict[str, Any]:
    response = await _get(client, token, username)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _refused(client: AsyncClient, token: str, username: str) -> None:
    response = await _get(client, token, username)
    assert response.status_code == 404, response.text
    assert response.json() == NOBODY


async def _views(db: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    rows = await db.execute(
        select(ProfileView.viewer_id, ProfileView.viewed_id).execution_options(
            populate_existing=True
        )
    )
    return [(row[0], row[1]) for row in rows]


async def test_a_username_opens_the_same_profile_as_its_id(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(2), username="simran.k")
    her_id = her.id

    by_name = await _ok(client, token, "simran.k")
    by_id = (await client.get(f"/v1/users/{her_id}", headers=bearer(token))).json()

    assert by_name == by_id
    assert by_name["id"] == str(her_id)


async def test_any_case_finds_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), username="noor_s")
    her_id = str(her.id)

    assert (await _ok(client, token, "Noor_S"))["id"] == her_id


async def test_a_link_reaches_past_seeking_and_the_radius(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE, seeking=Seeking.WOMEN)
    await person(db, make_user, Gender.MALE, at=(12.97, 77.59), username="far_man")

    assert (await _ok(client, token, "far_man"))["username"] == "far_man"


async def test_a_view_is_recorded_but_never_for_your_own(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE, username="its_me")
    her, _ = await person(db, make_user, at=north(1), username="viewed_one")
    me_id, her_id = me.id, her.id

    await _ok(client, token, "its_me")
    assert await _views(db) == []
    await _ok(client, token, "viewed_one")
    assert await _views(db) == [(me_id, her_id)]


async def test_your_own_opens_even_hidden(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await person(db, make_user, Gender.MALE)
    _, token = await person(db, make_user, username="hidden_me", is_hidden=True)

    assert (await _ok(client, token, "hidden_me"))["username"] == "hidden_me"


async def test_a_hidden_profile_opens_to_its_match_only(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-493's exception holds by username as by id."""
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), username="hid_n", is_hidden=True)
    _, strangers = await person(db, make_user, Gender.MALE, at=north(1))
    low, high = (me.id, her.id) if me.id.bytes < her.id.bytes else (her.id, me.id)
    await db.execute(
        text("INSERT INTO matches (id, user_low, user_high) VALUES (:id, :l, :h)"),
        {"id": uuid.uuid4(), "l": low, "h": high},
    )

    assert (await _ok(client, token, "hid_n"))["username"] == "hid_n"
    await _refused(client, strangers, "hid_n")


@pytest.mark.parametrize(
    "username",
    ["nobody_here", "no", "x" * 21, "bad!name", "..", "%25", "ab_d", "abc%25"],
)
async def test_a_name_nobody_holds_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, username: str
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    # `ab_d` must not reach `abcd`, nor `abc%` `abcde`, through a wildcard.
    await person(db, make_user, at=north(1), username="abcd")
    await person(db, make_user, at=north(1), username="abcde")

    await _refused(client, token, username)


async def test_every_refusal_is_the_same_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    await person(db, make_user, username="r_hidden", is_hidden=True)
    blocked_by_me, _ = await person(db, make_user, username="r_blocked_by")
    blocked_me, _ = await person(db, make_user, username="r_blocked_me")
    frozen, _ = await person(db, make_user, username="r_frozen")
    shadowed, _ = await person(db, make_user, username="r_shadow")
    await block(db, me, blocked_by_me)
    await block(db, blocked_me, me)
    await banded(db, frozen, FraudBand.FREEZE)
    await banded(db, shadowed, FraudBand.SHADOW)
    await db.flush()

    for name in ("r_hidden", "r_blocked_by", "r_blocked_me", "r_frozen", "r_shadow"):
        await _refused(client, token, name)


@pytest.mark.parametrize(
    "status", [s for s in UserStatus if s is not UserStatus.ACTIVE]
)
async def test_an_account_not_active_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: UserStatus
) -> None:
    """T-9.6, D-500: deleted or paused, not found."""
    _, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1), username="not_active")
    her.status = status
    await db.flush()

    await _refused(client, token, "not_active")


async def test_an_erased_name_is_free_and_finds_its_new_holder(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-505: at the erasure the username goes with the profile, so the next
    to take it is who it finds."""
    _, token = await person(db, make_user, Gender.MALE)
    old, _ = await person(db, make_user, at=north(1), username="taken_once")
    old.status = UserStatus.DELETED
    profile = await db.get(Profile, old.id)
    assert profile is not None
    await db.delete(profile)
    await db.flush()
    await _refused(client, token, "taken_once")

    new, _ = await person(db, make_user, at=north(1), username="taken_once")
    new_id = str(new.id)

    assert (await _ok(client, token, "taken_once"))["id"] == new_id


async def test_it_needs_sign_in_and_onboarding_done(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await person(db, make_user, at=north(1), username="someone")

    response = await client.get("/v1/users/by-username/someone")

    assert response.status_code == 401
