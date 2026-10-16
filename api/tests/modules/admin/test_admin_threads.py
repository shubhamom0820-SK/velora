"""`GET /v1/admin/threads/{id}/messages` (T-9.5, D-924): every message of the
Thread, oldest first, what either person cleared included (T-7.8, D-006), the
text as written where masking changed it, each page's read audited with the
reason staff gave (`?reason=`, at least 10 characters).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import MessageKind, Role
from app.modules.messages.models import Message
from app.modules.threads.models import ThreadClear
from tests.conftest import MakeThread, MakeUser
from tests.modules.admin.support import ADMIN, REASON, audits, auth, error, staff

pytestmark = pytest.mark.usefixtures("test_redis")


def _path(thread_id: uuid.UUID) -> str:
    return f"{ADMIN}/threads/{thread_id}/messages"


async def _read(
    client: AsyncClient,
    token: str,
    thread_id: uuid.UUID,
    **params: str | int,
) -> Response:
    return await client.get(
        _path(thread_id), params={"reason": REASON, **params}, headers=auth(token)
    )


async def test_every_message_shows_whatever_either_person_cleared(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    woman, _ = await make_user("female")
    thread = await make_thread(man, woman, messages=3)
    thread_id = thread.id
    for person in (man, woman):
        db.add(
            ThreadClear(user_id=person.id, thread_id=thread_id, cleared_at=clock.now())
        )
    await db.flush()

    response = await _read(client, token, thread_id)

    assert response.status_code == 200, response.text
    assert [m["body"] for m in response.json()["items"]] == [
        "Message 1",
        "Message 2",
        "Message 3",
    ]
    [entry] = await audits(db, moderator_id, "thread.read")
    assert (entry.target_type, entry.target_id, entry.meta) == (
        "thread",
        thread_id,
        {"reason": REASON},
    )


async def test_a_masked_message_is_read_as_written_and_a_voice_note_is_linked(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    woman, _ = await make_user("female")
    thread = await make_thread(man, woman)
    thread_id, man_id = thread.id, man.id
    db.add_all(
        [
            Message(
                thread_id=thread_id,
                sender_id=man_id,
                kind=MessageKind.TEXT,
                body="call me on ••••••••••",
                body_raw="call me on 9812345678",
                masked=True,
                client_msg_id=uuid.uuid4(),
                created_at=clock.now() - timedelta(seconds=1),
            ),
            Message(
                thread_id=thread_id,
                sender_id=man_id,
                kind=MessageKind.VOICE,
                media_key=f"voice/{thread_id}/one.webm",
                duration_s=7,
                client_msg_id=uuid.uuid4(),
            ),
        ]
    )
    await db.flush()

    response = await _read(client, token, thread_id)

    text, voice = response.json()["items"]
    assert (text["body"], text["masked"]) == ("call me on 9812345678", True)
    assert voice["duration_s"] == 7
    assert voice["audio_url"].startswith("fake-storage://velora-private/voice/")


async def test_a_page_at_a_time_each_read_audited(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    woman, _ = await make_user("female")
    thread = await make_thread(man, woman, messages=3)
    thread_id = thread.id

    first = await _read(client, token, thread_id, limit=2)
    second = await _read(
        client, token, thread_id, limit=2, cursor=first.json()["next_cursor"]
    )

    assert [m["body"] for m in first.json()["items"]] == ["Message 1", "Message 2"]
    assert [m["body"] for m in second.json()["items"]] == ["Message 3"]
    assert second.json()["next_cursor"] is None
    assert len(await audits(db, moderator_id, "thread.read")) == 2


@pytest.mark.parametrize("reason", [None, "too short", " " * 12])
async def test_a_read_without_a_reason_is_refused_and_unwritten(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    reason: str | None,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    man, _ = await make_user()
    woman, _ = await make_user("female")
    thread = await make_thread(man, woman, messages=1)
    params = {} if reason is None else {"reason": reason}

    response = await client.get(_path(thread.id), params=params, headers=auth(token))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await audits(db, moderator_id) == []


async def test_an_unknown_thread_is_not_found_and_unwritten(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)

    response = await _read(client, token, uuid.uuid4())

    assert response.status_code == 404
    assert await audits(db, moderator_id) == []
