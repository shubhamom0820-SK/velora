"""`POST /v1/media/voice-upload-url` (T-7.9, D-620): a woman's alone (D-010),
in a Thread of hers, for one of three types; a URL that lasts 5 minutes and
can't take more than 2 MB unnoticed (the send checks the size)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, ThreadStatus
from app.core.storage_keys import voice_upload_key
from app.modules.safety.models import Block
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")

PRIVATE = make_test_settings().R2_BUCKET_PRIVATE


async def _ask(
    client: AsyncClient,
    token: str,
    thread_id: uuid.UUID,
    content_type: str = "audio/webm",
) -> Response:
    return await client.post(
        "/v1/media/voice-upload-url",
        json={"thread_id": str(thread_id), "content_type": content_type},
        headers=bearer(token),
    )


@pytest.mark.parametrize(
    ("content_type", "extension"),
    [("audio/webm", "webm"), ("audio/ogg", "ogg"), ("audio/mp4", "m4a")],
)
async def test_she_gets_a_place_for_one_voice_note(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    content_type: str,
    extension: str,
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)

    response = await _ask(client, token, thread.id, content_type)

    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    message_id = uuid.UUID(body["message_id"])
    assert body["media_key"] == voice_upload_key(thread.id, message_id, content_type)  # type: ignore[arg-type]
    assert body["media_key"].endswith(f".{extension}")
    # Signed for exactly this type, for 5 minutes (D-027), sized at 2 MB.
    assert body["put_url"] == (
        f"fake-storage://{PRIVATE}/{body['media_key']}"
        f"?method=PUT&ttl=300&max_bytes={2 * 1024 * 1024}"
    )
    assert body["headers"] == {"Content-Type": content_type}


async def test_each_url_is_a_new_place(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)

    first = (await _ask(client, token, thread.id)).json()
    second = (await _ask(client, token, thread.id)).json()

    assert first["message_id"] != second["message_id"]


async def test_a_man_is_not_allowed(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)

    response = await _ask(client, token, thread.id)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"


@pytest.mark.parametrize(
    "content_type", ["audio/mpeg", "audio/webm;codecs=opus", "image/jpeg", "AUDIO/WEBM"]
)
async def test_any_other_type_is_refused_saying_which_are_accepted(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    content_type: str,
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)

    response = await _ask(client, token, thread.id, content_type)

    assert response.status_code == 422
    found = error(response)
    assert found["code"] == "UNSUPPORTED_AUDIO"
    assert found["details"] == {"accepted": ["audio/webm", "audio/ogg", "audio/mp4"]}


async def test_a_thread_not_hers_is_not_found(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    other, _ = await make_user(Gender.FEMALE)
    _, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, other)

    for thread_id in (thread.id, uuid.uuid4()):
        response = await _ask(client, token, thread_id)
        assert response.status_code == 404
        assert error(response)["code"] == "NOT_FOUND"


async def test_across_a_block_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    db.add(Block(blocker_id=man.id, blocked_id=woman.id))
    await db.flush()

    response = await _ask(client, token, thread.id)

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


async def test_an_expired_thread_still_takes_hers(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-097: an expired Thread accepts her messages, so her voice note too."""
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status=ThreadStatus.EXPIRED)

    response = await _ask(client, token, thread.id)

    assert response.status_code == 200, response.text
