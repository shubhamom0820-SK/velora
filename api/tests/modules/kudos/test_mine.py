"""`GET /v1/me/kudos` (T-8.5, D-680): the kinds you were given, each with how
many gave it; never who, nor when; yours to see whether you show them or not.
And what `POST /v1/kudos` gives is what a public profile counts, while its
owner shows them (`show_kudos`, T-6.3)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, error
from tests.modules.kudos.test_give import _give, _talked

pytestmark = pytest.mark.usefixtures("test_redis")


async def _mine(client: AsyncClient, token: str) -> list[dict[str, object]]:
    response = await client.get("/v1/me/kudos", headers=bearer(token))
    assert response.status_code == 200, response.text
    found: list[dict[str, object]] = response.json()
    return found


async def _from(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    to: User,
    kind: str,
) -> User:
    """A man who talked with `to` and gave them `kind`."""
    giver, token = await make_user()
    await _talked(db, make_thread, giver, to)
    assert (await _give(client, token, to.id, kind)).status_code == 201
    return giver


async def test_mine_are_counts_by_kind_of_those_received_only(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    woman, token = await make_user(Gender.FEMALE)
    for kind in ("really_thoughtful", "genuinely_funny", "really_thoughtful"):
        await _from(db, client, make_user, make_thread, woman, kind)
    # One she gave, which is never among hers.
    man, _ = await make_user()
    await _talked(db, make_thread, man, woman)
    assert (await _give(client, token, man.id, "easy_to_talk_to")).status_code == 201

    assert await _mine(client, token) == [
        {"kind": "genuinely_funny", "count": 1},
        {"kind": "really_thoughtful", "count": 2},
    ]


async def test_none_yet_is_an_empty_list(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    assert await _mine(client, token) == []


async def test_mine_show_even_while_hidden_from_my_profile(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    woman, token = await make_user(Gender.FEMALE)
    await _from(db, client, make_user, make_thread, woman, "great_conversation")
    profile = await db.get(Profile, woman.id)
    assert profile is not None
    profile.show_kudos = False
    await db.flush()

    assert await _mine(client, token) == [{"kind": "great_conversation", "count": 1}]


async def test_a_profile_counts_them_while_shown_and_never_says_who(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    woman, own = await make_user(Gender.FEMALE)
    giver = await _from(db, client, make_user, make_thread, woman, "genuinely_funny")

    response = await client.get(f"/v1/users/{woman.id}", headers=bearer(own))
    assert response.status_code == 200, response.text
    assert response.json()["kudos"] == {
        "great_conversation": 0,
        "genuinely_funny": 1,
        "easy_to_talk_to": 0,
        "really_thoughtful": 0,
    }
    mine = await client.get("/v1/me/kudos", headers=bearer(own))
    assert str(giver.id) not in response.text
    assert str(giver.id) not in mine.text

    profile = await db.get(Profile, woman.id)
    assert profile is not None
    profile.show_kudos = False
    await db.flush()
    hidden = await client.get(f"/v1/users/{woman.id}", headers=bearer(own))
    assert hidden.json()["kudos"] is None


async def test_mine_needs_onboarding_done(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await client.get("/v1/me/kudos", headers=bearer(token))

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"
