"""`GET /v1/threads/{id}/messages` (T-7.3): newest first, after my clearing
only (D-006); a deleted account's messages stay, named as such (D-051); a
voice note locked for a man until he unlocks it, never its file; never the
original text."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, MessageKind, UserStatus
from app.modules.messages.models import Message, MessageUnlock
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")


async def _read(
    client: AsyncClient, token: str, thread_id: uuid.UUID, **q: Any
) -> Response:
    return await client.get(
        f"/v1/threads/{thread_id}/messages", params=q, headers=bearer(token)
    )


async def _items(
    client: AsyncClient, token: str, thread_id: uuid.UUID
) -> list[dict[str, Any]]:
    response = await _read(client, token, thread_id)
    assert response.status_code == 200, response.text
    assert response.json()["next_cursor"] is None
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def _say(
    db: AsyncSession,
    thread: Thread,
    sender: User,
    body: str | None = "Hello",
    *,
    ago: timedelta = timedelta(0),
    kind: MessageKind = MessageKind.TEXT,
    body_raw: str | None = None,
) -> Message:
    message = Message(
        thread_id=thread.id,
        sender_id=sender.id,
        kind=kind,
        body=body,
        body_raw=body_raw,
        masked=body_raw is not None,
        media_key="voice/x.webm" if kind is MessageKind.VOICE else None,
        duration_s=12 if kind is MessageKind.VOICE else None,
        client_msg_id=uuid.uuid4(),
        created_at=clock.now() - ago,
    )
    db.add(message)
    await db.flush()
    return message


async def test_newest_first_each_as_mine_or_theirs_never_the_original(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    old = await _say(db, thread, man, "First", ago=timedelta(minutes=2))
    new = await _say(db, thread, woman, "call ••••••••••", body_raw="call 9876543210")

    items = await _items(client, token, thread.id)

    assert [item["id"] for item in items] == [str(new.id), str(old.id)]
    assert (items[0]["mine"], items[1]["mine"]) == (False, True)
    assert items[0]["body"] == "call ••••••••••" and items[0]["masked"] is True
    assert items[0]["client_msg_id"] is None
    assert items[1]["client_msg_id"] == str(old.client_msg_id)
    for item in items:
        assert "body_raw" not in item
        assert "9876543210" not in str(item)


async def test_only_what_came_after_my_clearing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    before = await _say(db, thread, woman, "Before", ago=timedelta(hours=2))
    after = await _say(db, thread, woman, "After")
    db.add(
        ThreadClear(
            user_id=man.id,
            thread_id=thread.id,
            cleared_at=clock.now() - timedelta(hours=1),
        )
    )
    await db.flush()

    mine = await _items(client, token, thread.id)
    hers = await _items(client, her_token, thread.id)

    assert [item["id"] for item in mine] == [str(after.id)]
    # One-sided (D-006): she still has both.
    assert [item["id"] for item in hers] == [str(after.id), str(before.id)]


async def test_a_deleted_accounts_messages_stay_and_say_so(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, "Still here")
    await db.execute(
        update(User)
        .where(User.id == woman.id)
        .values(status=UserStatus.DELETED, deleted_requested_at=clock.now())
    )

    [item] = await _items(client, token, thread.id)

    assert item["body"] == "Still here"
    assert item["from_deleted_account"] is True


async def test_her_voice_note_is_locked_for_him_until_he_unlocks_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    note = await _say(db, thread, woman, None, kind=MessageKind.VOICE)

    [locked] = await _items(client, token, thread.id)
    [hers] = await _items(client, her_token, thread.id)
    db.add(MessageUnlock(user_id=man.id, message_id=note.id))
    await db.flush()
    [unlocked] = await _items(client, token, thread.id)

    assert locked["kind"] == "voice" and locked["locked"] is True
    assert locked["duration_s"] == 12
    assert hers["locked"] is False  # her own
    assert unlocked["locked"] is False
    # Never the file, locked or not (T-7.9 serves it).
    for item in (locked, hers, unlocked):
        assert "voice/x.webm" not in str(item)
        assert "media_key" not in item


async def test_a_woman_never_has_to_unlock(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    woman, token = await make_user(Gender.FEMALE)
    other, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, other)
    await _say(db, thread, other, None, kind=MessageKind.VOICE)

    [item] = await _items(client, token, thread.id)

    assert item["locked"] is False


async def test_pages_follow_the_cursor(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    said = [
        await _say(db, thread, woman, f"{n}", ago=timedelta(minutes=n))
        for n in range(3)
    ]

    first = await _read(client, token, thread.id, limit=2)
    second = await _read(
        client, token, thread.id, limit=2, cursor=first.json()["next_cursor"]
    )

    assert [i["id"] for i in first.json()["items"]] == [
        str(said[0].id),
        str(said[1].id),
    ]
    assert [i["id"] for i in second.json()["items"]] == [str(said[2].id)]
    assert second.json()["next_cursor"] is None


async def test_someone_elses_thread_or_one_across_a_block_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    _, stranger = await make_user()
    thread_id = (await make_thread(man, woman)).id
    await block(db, woman, man)

    for who, target in (
        (stranger, thread_id),
        (token, thread_id),
        (token, uuid.uuid4()),
    ):
        response = await _read(client, who, target)
        assert response.status_code == 404
        assert error(response)["code"] == "NOT_FOUND"


@pytest.mark.parametrize("query", [{"limit": 0}, {"limit": 51}, {"cursor": "nope"}])
async def test_a_bad_query_is_a_validation_error(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    query: dict[str, Any],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id

    response = await _read(client, token, thread_id, **query)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
