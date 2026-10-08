"""A block's effects, made through `POST /v1/blocks` (T-9.1; 06-TESTING's
critical 9): from the moment it commits, neither person appears to the other
anywhere, and everything between them is `NOT_FOUND` (D-862), whichever of
them blocked. Unblocking lifts every one of them, and brings a Thread back
exactly as it was: a clearing still in place.

Each surface is one entry in `_SURFACES`, asked the same way of both people,
so a surface that forgot the block, either way, fails by name. What is already
proved surface by surface with a block row written directly (the typing relay,
kudos, gifts, voice notes) stays in those modules; this proves the endpoint's
block is the block they read."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, MessageKind
from app.modules.messages.models import Message
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, north, person, swipe
from tests.modules.safety.support import blocked, unblocked

pytestmark = [pytest.mark.usefixtures("test_redis"), pytest.mark.critical]


@dataclass
class Side:
    """One of the two, as the other is seen from their side."""

    token: str
    other_id: uuid.UUID
    other_username: str
    thread_id: uuid.UUID


async def _ok_ids(
    client: AsyncClient, side: Side, path: str, **params: Any
) -> list[str]:
    """The ids a list gives: each item's own, or its card's (search's rows
    are cards; the chats list's rows are Threads)."""
    response = await client.get(path, params=params, headers=bearer(side.token))
    assert response.status_code == 200, (path, response.text)
    found: list[str] = [item["id"] for item in response.json()["items"]]
    return found


async def _feed(client: AsyncClient, side: Side) -> bool:
    return str(side.other_id) in await _ok_ids(client, side, "/v1/discover", limit=50)


async def _search(client: AsyncClient, side: Side) -> bool:
    found = await _ok_ids(client, side, "/v1/search", q=f"@{side.other_username}")
    return str(side.other_id) in found


async def _status(client: AsyncClient, side: Side, path: str) -> bool:
    response = await client.get(path, headers=bearer(side.token))
    assert response.status_code in (200, 404), (path, response.text)
    if response.status_code == 404:
        assert response.json()["error"]["code"] == "NOT_FOUND", path
    return response.status_code == 200


async def _profile(client: AsyncClient, side: Side) -> bool:
    return await _status(client, side, f"/v1/users/{side.other_id}")


async def _by_username(client: AsyncClient, side: Side) -> bool:
    return await _status(client, side, f"/v1/users/by-username/{side.other_username}")


async def _album(client: AsyncClient, side: Side) -> bool:
    return await _status(client, side, f"/v1/users/{side.other_id}/album")


async def _gifts(client: AsyncClient, side: Side) -> bool:
    return await _status(client, side, f"/v1/users/{side.other_id}/gifts")


async def _chats(client: AsyncClient, side: Side) -> bool:
    return str(side.thread_id) in await _ok_ids(client, side, "/v1/threads")


async def _thread(client: AsyncClient, side: Side) -> bool:
    return await _status(client, side, f"/v1/threads/{side.thread_id}")


async def _messages(client: AsyncClient, side: Side) -> bool:
    return await _status(client, side, f"/v1/threads/{side.thread_id}/messages")


async def _send(client: AsyncClient, side: Side) -> bool:
    """Asked last: a message sent moves the Thread, which nothing above minds."""
    response = await client.post(
        f"/v1/threads/{side.thread_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hi"},
        headers=bearer(side.token),
    )
    assert response.status_code in (200, 404), response.text
    if response.status_code == 404:
        assert response.json()["error"]["code"] == "NOT_FOUND"
    return response.status_code == 200


Surface = Callable[[AsyncClient, Side], Awaitable[bool]]
_SURFACES: dict[str, Surface] = {
    "feed": _feed,
    "search": _search,
    "profile": _profile,
    "profile by username": _by_username,
    "album": _album,
    "gifts": _gifts,
    "chats list": _chats,
    "thread": _thread,
    "messages": _messages,
    "send": _send,
}


async def _seen(client: AsyncClient, side: Side) -> dict[str, bool]:
    return {name: await surface(client, side) for name, surface in _SURFACES.items()}


async def _pair(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread
) -> tuple[User, str, User, str, Side, Side]:
    """A man and a woman near each other, wanting each other, neither swiped
    yet (the feed leaves out whom you swiped), and a live Thread between them,
    in which he writes free (D-551)."""
    man, man_token = await person(db, make_user, Gender.MALE, username="block_him")
    woman, woman_token = await person(
        db, make_user, Gender.FEMALE, at=north(1), username="block_her"
    )
    thread = await make_thread(man, woman, messages=2)
    db.add(
        Message(
            thread_id=thread.id,
            sender_id=woman.id,
            kind=MessageKind.TEXT,
            body="Hers",
            client_msg_id=uuid.uuid4(),
        )
    )
    await db.flush()
    his = Side(man_token, woman.id, "block_her", thread.id)
    hers = Side(woman_token, man.id, "block_him", thread.id)
    return man, man_token, woman, woman_token, his, hers


EVERYWHERE = dict.fromkeys(_SURFACES, True)
NOWHERE = dict.fromkeys(_SURFACES, False)


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_after_a_block_neither_appears_to_the_other_anywhere(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    who_blocks: str,
) -> None:
    man, man_token, woman, woman_token, his, hers = await _pair(
        db, make_user, make_thread
    )
    man_id, woman_id = man.id, woman.id
    # Before: each sees the other everywhere, so every "no" below is the block.
    before = {
        name: v for name, v in (await _seen(client, his)).items() if name != "send"
    }
    assert before == {k: v for k, v in EVERYWHERE.items() if k != "send"}

    if who_blocks == "her":
        await blocked(client, woman_token, man_id)
    else:
        await blocked(client, man_token, woman_id)

    assert await _seen(client, his) == NOWHERE
    assert await _seen(client, hers) == NOWHERE


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_unblocking_lifts_every_one_of_them(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    who_blocks: str,
) -> None:
    man, man_token, woman, woman_token, his, hers = await _pair(
        db, make_user, make_thread
    )
    blocker, other = (
        (woman_token, man.id) if who_blocks == "her" else (man_token, woman.id)
    )
    await blocked(client, blocker, other)

    await unblocked(client, blocker, other)

    assert await _seen(client, his) == EVERYWHERE
    assert await _seen(client, hers) == EVERYWHERE


async def test_a_block_by_each_needs_both_lifted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, man_token, woman, woman_token, his, hers = await _pair(
        db, make_user, make_thread
    )
    man_id, woman_id = man.id, woman.id
    await blocked(client, man_token, woman_id)
    await blocked(client, woman_token, man_id)

    await unblocked(client, man_token, woman_id)

    assert await _seen(client, his) == NOWHERE
    assert await _seen(client, hers) == NOWHERE


# --- A clearing, under a block (T-7.8, D-610) -----------------------------------------


async def _bodies(client: AsyncClient, token: str, thread_id: uuid.UUID) -> list[str]:
    response = await client.get(
        f"/v1/threads/{thread_id}/messages", headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    return [m["body"] for m in response.json()["items"]]


async def test_a_block_hides_a_thread_apart_from_a_clearing_which_survives_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """She clears, then blocks, then unblocks: the Thread is back as her
    clearing left it, hidden from her chats with nothing newer, its messages
    from after her clearing only; his side never changed."""
    man, man_token, _, woman_token, his, hers = await _pair(db, make_user, make_thread)
    man_id, thread_id = man.id, his.thread_id
    cleared = await client.post(
        f"/v1/threads/{thread_id}/clear", headers=bearer(woman_token)
    )
    assert cleared.status_code == 204, cleared.text
    his_before = await _bodies(client, man_token, thread_id)

    await blocked(client, woman_token, man_id)
    await unblocked(client, woman_token, man_id)

    assert not await _chats(client, hers)
    assert await _bodies(client, woman_token, thread_id) == []
    assert await _chats(client, his)
    assert await _bodies(client, man_token, thread_id) == his_before
    restored = await client.delete(
        f"/v1/threads/{thread_id}/clear", headers=bearer(woman_token)
    )
    assert restored.status_code == 204
    assert sorted(await _bodies(client, woman_token, thread_id)) == sorted(his_before)


async def _likes(client: AsyncClient, token: str) -> int:
    response = await client.get("/v1/likes/count", headers=bearer(token))
    assert response.status_code == 200, response.text
    count: int = response.json()["count"]
    return count


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_a_like_from_across_a_block_is_gone_from_liked_you_until_lifted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, who_blocks: str
) -> None:
    """Liked you is the one surface a swipe takes someone into rather than out
    of, so it is asked apart: she likes him, and he sees it, until a block."""
    man, man_token = await person(db, make_user, Gender.MALE)
    woman, woman_token = await person(db, make_user, Gender.FEMALE, at=north(1))
    await swipe(db, woman, man, "like")
    man_id, woman_id = man.id, woman.id
    blocker, other = (
        (woman_token, man_id) if who_blocks == "her" else (man_token, woman_id)
    )
    assert await _likes(client, man_token) == 1

    await blocked(client, blocker, other)
    assert await _likes(client, man_token) == 0
    response = await client.get("/v1/likes", headers=bearer(man_token))
    assert response.json()["items"] == []

    await unblocked(client, blocker, other)
    assert await _likes(client, man_token) == 1
