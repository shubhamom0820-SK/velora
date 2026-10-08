"""`PublicProfile.thread.kudos` (T-8.8, D-790, P-580): whether the viewer may
give the person kudos in their Thread, so the web's prompt shows only when
`POST /kudos` would take it. `given` once they have, of any kind;
`too_early` until both have written and the Thread has `kudos_min_messages`
messages (D-680, the rule `POST /kudos` reads); else `can_give`."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, north, person
from tests.modules.kudos.test_give import _config, _give, _talked

pytestmark = pytest.mark.usefixtures("test_redis")


async def _thread_with(client: AsyncClient, token: str, other: uuid.UUID) -> Any:
    response = await client.get(f"/v1/users/{other}", headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()["thread"]


async def _pair(db: AsyncSession, make_user: MakeUser) -> tuple[User, str, User, str]:
    man, his = await person(db, make_user, Gender.MALE)
    woman, hers = await person(db, make_user, at=north(1))
    return man, his, woman, hers


async def test_a_conversation_both_ways_can_give(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his, woman, hers = await _pair(db, make_user)
    man_id, woman_id = man.id, woman.id
    await _talked(db, make_thread, man, woman, mine=5, theirs=1)

    assert (await _thread_with(client, his, woman_id))["kudos"] == "can_give"
    assert (await _thread_with(client, hers, man_id))["kudos"] == "can_give"


async def test_five_messages_are_too_early_and_six_enough(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his, early, _ = await _pair(db, make_user)
    ready, _ = await person(db, make_user, at=north(2))
    early_id, ready_id = early.id, ready.id
    await _talked(db, make_thread, man, early, mine=4, theirs=1)
    await _talked(db, make_thread, man, ready, mine=5, theirs=1)

    assert (await _thread_with(client, his, early_id))["kudos"] == "too_early"
    assert (await _thread_with(client, his, ready_id))["kudos"] == "can_give"


async def test_the_least_is_read_from_app_config(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his, woman, _ = await _pair(db, make_user)
    woman_id = woman.id
    await _talked(db, make_thread, man, woman, mine=5, theirs=1)
    await _config(db, "kudos_min_messages", 7)

    assert (await _thread_with(client, his, woman_id))["kudos"] == "too_early"

    await _config(db, "kudos_min_messages", 2)

    assert (await _thread_with(client, his, woman_id))["kudos"] == "can_give"


async def test_a_one_sided_thread_is_too_early_for_either(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his, woman, hers = await _pair(db, make_user)
    man_id, woman_id = man.id, woman.id
    # Ten from him and none from her: a monologue, not a conversation (D-680).
    await _talked(db, make_thread, man, woman, mine=10, theirs=0)

    assert (await _thread_with(client, his, woman_id))["kudos"] == "too_early"
    assert (await _thread_with(client, hers, man_id))["kudos"] == "too_early"


async def test_given_once_given_whatever_its_kind_and_only_for_the_giver(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his, woman, hers = await _pair(db, make_user)
    man_id, woman_id = man.id, woman.id
    await _talked(db, make_thread, man, woman, mine=5, theirs=1)

    assert (await _give(client, his, woman_id, "really_thoughtful")).status_code == 201

    assert (await _thread_with(client, his, woman_id))["kudos"] == "given"
    # Kudos the other way is hers to give, still open to her.
    assert (await _thread_with(client, hers, man_id))["kudos"] == "can_give"


async def test_what_the_profile_says_is_what_post_kudos_does(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """The prompt never shows only to be refused: each state, then the give."""
    man, his, early, _ = await _pair(db, make_user)
    ready, _ = await person(db, make_user, at=north(2))
    early_id, ready_id = early.id, ready.id
    await _talked(db, make_thread, man, early, mine=3, theirs=1)
    await _talked(db, make_thread, man, ready, mine=5, theirs=1)

    assert (await _thread_with(client, his, early_id))["kudos"] == "too_early"
    assert (await _give(client, his, early_id)).status_code == 422
    assert (await _thread_with(client, his, ready_id))["kudos"] == "can_give"
    assert (await _give(client, his, ready_id)).status_code == 201
    assert (await _thread_with(client, his, ready_id))["kudos"] == "given"
    assert (await _give(client, his, ready_id)).status_code == 409
