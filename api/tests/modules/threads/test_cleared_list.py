"""`GET /v1/threads/cleared` (T-9.8, P-510, D-912): the chats I cleared that
nothing newer has brought back, Threads and Knots alike, newest clearing
first, never one across a block either way, never anyone else's clearing.
Each leaves the list when a message brings it back or I restore it (D-611)."""

from __future__ import annotations

import base64
import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, MessageKind, ThreadStatus
from app.modules.messages.models import Message
from app.modules.threads.models import Thread
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")


async def _say(
    db: AsyncSession, thread: Thread, sender: User, *, ago: timedelta = timedelta(0)
) -> None:
    """A text message `ago` before now, the Thread's last if newest."""
    at = clock.now() - ago
    db.add(
        Message(
            thread_id=thread.id,
            sender_id=sender.id,
            kind=MessageKind.TEXT,
            body="Hello",
            body_raw="raw Hello",
            client_msg_id=uuid.uuid4(),
            created_at=at,
        )
    )
    thread.message_count += 1
    if thread.last_message_at is None or at > thread.last_message_at:
        thread.last_message_at = at
    await db.flush()


async def _clear(client: AsyncClient, token: str, thread_id: uuid.UUID) -> None:
    response = await client.post(
        f"/v1/threads/{thread_id}/clear", headers=bearer(token)
    )
    assert response.status_code == 204, response.text


async def _cleared(client: AsyncClient, token: str, **params: Any) -> Response:
    return await client.get("/v1/threads/cleared", params=params, headers=bearer(token))


async def _ids(client: AsyncClient, token: str) -> list[str]:
    response = await _cleared(client, token)
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


@pytest.mark.critical
async def test_a_cleared_chat_is_listed_until_a_message_or_a_restore_brings_it_back(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    three, _ = await make_user(Gender.FEMALE)
    talked = await make_thread(man, one)
    await _say(db, talked, one, ago=timedelta(hours=1))
    quiet = await make_thread(man, two)
    kept = await make_thread(man, three)
    talked_id, quiet_id, kept_id = talked.id, quiet.id, kept.id
    await _clear(client, token, talked_id)
    await _clear(client, token, quiet_id)

    response = await _cleared(client, token)

    assert response.status_code == 200, response.text
    body = response.json()
    # Newest clearing first: a clearing reaches the newest message (D-610),
    # an hour ago for one, the opening, just now, for the other.
    assert [row["id"] for row in body["items"]] == [str(quiet_id), str(talked_id)]
    assert body["next_cursor"] is None
    row = body["items"][1]
    assert row["other"]["id"] == str(one.id)
    assert row["unread"] == 0
    assert str(kept_id) not in await _ids(client, token)

    # A message brings it back to the chats, so it leaves this list.
    await _say(db, talked, one)
    assert await _ids(client, token) == [str(quiet_id)]
    # A restore brings it back too.
    restored = await client.delete(
        f"/v1/threads/{quiet_id}/clear", headers=bearer(token)
    )
    assert restored.status_code == 204
    assert await _ids(client, token) == []


async def test_a_cleared_knot_is_listed_too(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    knot = await make_thread(man, woman, status=ThreadStatus.KNOTTED)
    knot_id = knot.id
    await _clear(client, token, knot_id)

    [row] = (await _cleared(client, token)).json()["items"]

    assert row["id"] == str(knot_id)
    assert row["status"] == "knotted"


@pytest.mark.critical
async def test_only_my_own_clearing_is_listed(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """A clearing is one person's view (D-006): hers never shows in his list,
    and neither does a Thread he isn't in."""
    man, his_token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    other, other_token = await make_user()
    thread = await make_thread(man, woman)
    theirs = await make_thread(other, woman)
    thread_id, theirs_id = thread.id, theirs.id
    await _clear(client, her_token, thread_id)
    await _clear(client, other_token, theirs_id)

    assert await _ids(client, his_token) == []
    assert await _ids(client, her_token) == [str(thread_id)]
    assert await _ids(client, other_token) == [str(theirs_id)]


@pytest.mark.critical
@pytest.mark.parametrize("blocker", ["me", "them"])
async def test_one_across_a_block_isnt_listed_and_an_unblock_brings_it_back(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    blocker: str,
) -> None:
    """Whoever blocked, the Thread is hidden from both (D-862), here too;
    unblocking brings it back with the clearing still in place (D-863)."""
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    thread_id, man_id, woman_id = thread.id, man.id, woman.id
    await _clear(client, token, thread_id)
    if blocker == "me":
        await block(db, man, woman)
        lift, lifter, lifted = token, man_id, woman_id
    else:
        await block(db, woman, man)
        lift, lifter, lifted = her_token, woman_id, man_id

    assert await _ids(client, token) == []

    response = await client.delete(f"/v1/blocks/{lifted}", headers=bearer(lift))
    assert response.status_code == 204, (lifter, response.text)
    assert await _ids(client, token) == [str(thread_id)]


async def test_the_list_pages_by_its_cursor_and_refuses_one_it_never_gave(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    for _n in range(3):
        woman, _ = await make_user(Gender.FEMALE)
        thread = await make_thread(man, woman)
        await _clear(client, token, thread.id)

    one = (await _cleared(client, token, limit=2)).json()
    two = (await _cleared(client, token, limit=2, cursor=one["next_cursor"])).json()

    seen = [row["id"] for row in one["items"] + two["items"]]
    assert len(seen) == len(set(seen)) == 3
    assert two["next_cursor"] is None
    for params in (
        {"cursor": base64.urlsafe_b64encode(b'["x"]').decode().rstrip("=")},
        {"limit": 0},
        {"limit": 51},
    ):
        response = await _cleared(client, token, **params)
        assert response.status_code == 400, params
        assert error(response)["code"] == "VALIDATION_ERROR"


async def test_signed_out_and_unfinished_onboarding_are_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, unfinished = await make_user(onboarded=False)

    signed_out = await client.get("/v1/threads/cleared")
    early = await client.get("/v1/threads/cleared", headers=bearer(unfinished))

    assert signed_out.status_code == 401
    assert error(signed_out)["code"] == "AUTH_REQUIRED"
    assert early.status_code == 403
    assert error(early)["code"] == "ONBOARDING_INCOMPLETE"
