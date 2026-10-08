"""Sending a voice note (T-7.9, D-620): hers alone (D-010); judged by its
bytes, never by the type or length the browser declares; 2 MB and 60 seconds
at most, the length measured; kept as the bytes measured, under a key no
client can write, so nothing can be swapped in after the check."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, MessageKind, ThreadStatus
from app.core.providers import FakeProviders
from app.core.providers.storage import FakeStorage, ObjectInfo
from app.core.storage_keys import voice_upload_key
from app.modules.messages.models import Message
from app.modules.threads.models import Thread
from app.modules.users.models import User
from tests import audio_samples as samples
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")

PRIVATE = make_test_settings().R2_BUCKET_PRIVATE
TWO_MB = 2 * 1024 * 1024


async def _upload(
    client: AsyncClient,
    storage: FakeStorage,
    token: str,
    thread_id: uuid.UUID,
    data: bytes,
    content_type: str = "audio/webm",
) -> dict[str, Any]:
    """Ask for the URL, and PUT `data` to it as the browser would."""
    response = await client.post(
        "/v1/media/voice-upload-url",
        json={"thread_id": str(thread_id), "content_type": content_type},
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    place: dict[str, Any] = response.json()
    await storage.put_bytes(PRIVATE, place["media_key"], data, content_type)
    return place


async def _send(
    client: AsyncClient,
    token: str,
    thread_id: uuid.UUID,
    media_key: str,
    *,
    client_msg_id: uuid.UUID | None = None,
    **extra: Any,
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(client_msg_id or uuid.uuid4()),
            "kind": "voice",
            "media_key": media_key,
            **extra,
        },
        headers=bearer(token),
    )


async def _voice_notes(db: AsyncSession, thread_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.thread_id == thread_id, Message.kind == MessageKind.VOICE)
    )
    return count or 0


async def _pair(
    make_user: MakeUser, make_thread: MakeThread, **kw: Any
) -> tuple[User, str, User, str, Thread]:
    man, man_token = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, **kw)
    return man, man_token, woman, token, thread


# --- Sent -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "content_type", "seconds"),
    [
        (samples.webm(12_340), "audio/webm", 12),
        (samples.ogg(41.6), "audio/ogg", 42),
        (samples.fragmented_mp4(9), "audio/mp4", 9),
        (samples.mp4(3.2), "audio/mp4", 3),
    ],
)
async def test_her_voice_note_is_kept_as_measured(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    published: list[events.Event],
    data: bytes,
    content_type: str,
    seconds: int,
) -> None:
    man, _, woman, token, thread = await _pair(make_user, make_thread)
    man_id, woman_id, thread_id = man.id, woman.id, thread.id
    storage = fake_providers.storage
    place = await _upload(client, storage, token, thread_id, data, content_type)

    # The client says 1 second; the file says otherwise, and the file decides.
    response = await _send(client, token, thread_id, place["media_key"], duration_s=1)

    assert response.status_code == 200, response.text
    body = response.json()
    [row] = await db.scalars(select(Message).where(Message.thread_id == thread_id))
    assert str(row.id) == body["id"] == place["message_id"]
    assert row.kind is MessageKind.VOICE
    assert row.duration_s == body["duration_s"] == seconds
    assert row.body is None and body["body"] is None
    assert body["locked"] is False and body["mine"] is True
    # Kept under a key of its own, the bytes measured; the upload is gone.
    assert row.media_key is not None
    assert row.media_key.startswith(f"voice/{thread_id}/")
    assert row.media_key != place["media_key"]
    assert storage.objects[(PRIVATE, row.media_key)].data == data
    assert storage.objects[(PRIVATE, row.media_key)].content_type == content_type
    assert (PRIVATE, place["media_key"]) not in storage.objects
    # Never the file's key in a Message.
    assert "media_key" not in body
    refreshed = await db.scalar(
        select(Thread)
        .where(Thread.id == thread_id)
        .execution_options(populate_existing=True)
    )
    assert refreshed is not None and refreshed.message_count == 1
    told = {e.user_id: e.data["message"] for e in published if e.type == "message.new"}
    assert told[woman_id]["locked"] is False
    assert told[man_id]["locked"] is True
    assert "media_key" not in told[man_id]


async def test_a_woman_receiving_one_hears_it_free(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    published: list[events.Event],
) -> None:
    other, _ = await make_user(Gender.FEMALE)
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(other, woman)
    other_id, thread_id = other.id, thread.id
    place = await _upload(
        client, fake_providers.storage, token, thread_id, samples.webm(3000)
    )

    response = await _send(client, token, thread_id, place["media_key"])

    assert response.status_code == 200, response.text
    told = {e.user_id: e.data["message"] for e in published if e.type == "message.new"}
    assert told[other_id]["locked"] is False


async def test_a_minute_and_a_frame_over_is_a_minute(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    """The web stops recording at 60 seconds; a frame's overrun passes."""
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    place = await _upload(
        client, fake_providers.storage, token, thread_id, samples.webm(60_400)
    )

    response = await _send(client, token, thread_id, place["media_key"])

    assert response.status_code == 200, response.text
    assert response.json()["duration_s"] == 60


async def test_an_expired_thread_takes_her_voice_note(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    _, _, _, token, thread = await _pair(
        make_user, make_thread, status=ThreadStatus.EXPIRED
    )
    thread_id = thread.id
    place = await _upload(
        client, fake_providers.storage, token, thread_id, samples.ogg(5), "audio/ogg"
    )

    response = await _send(client, token, thread_id, place["media_key"])

    assert response.status_code == 200, response.text
    assert await _voice_notes(db, thread_id) == 1


async def test_a_retried_send_returns_the_note_it_made(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    place = await _upload(
        client, fake_providers.storage, token, thread_id, samples.webm(4000)
    )
    client_msg_id = uuid.uuid4()

    first = await _send(
        client, token, thread_id, place["media_key"], client_msg_id=client_msg_id
    )
    again = await _send(
        client, token, thread_id, place["media_key"], client_msg_id=client_msg_id
    )

    assert first.status_code == again.status_code == 200, again.text
    assert again.json() == first.json()
    assert await _voice_notes(db, thread_id) == 1


async def test_a_put_again_after_the_send_changes_nothing_kept(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    """The upload URL lasts 5 minutes. A second PUT to it, sent again under a
    new id, is refused, and the file the first message keeps is untouched:
    what a man unlocks is what was checked."""
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    storage = fake_providers.storage
    first = samples.webm(4000)
    place = await _upload(client, storage, token, thread_id, first)
    sent = await _send(client, token, thread_id, place["media_key"])
    assert sent.status_code == 200, sent.text
    [row] = await db.scalars(select(Message).where(Message.thread_id == thread_id))
    kept_key = row.media_key
    assert kept_key is not None

    await storage.put_bytes(
        PRIVATE, place["media_key"], samples.webm(50_000), "audio/webm"
    )
    again = await _send(client, token, thread_id, place["media_key"])

    assert again.status_code == 409
    assert error(again)["code"] == "ALREADY_EXISTS"
    assert await _voice_notes(db, thread_id) == 1
    assert storage.objects[(PRIVATE, kept_key)].data == first


# --- Refused --------------------------------------------------------------------


async def test_a_man_cant_send_one(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    _, man_token, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    # Even with a key her URL gave, the bytes there and all.
    place = await _upload(
        client, fake_providers.storage, token, thread_id, samples.webm(3000)
    )

    response = await _send(client, man_token, thread_id, place["media_key"])

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert await _voice_notes(db, thread_id) == 0


async def test_over_a_minute_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    storage = fake_providers.storage
    place = await _upload(client, storage, token, thread_id, samples.webm(60_600))

    # The client's word, 60, changes nothing.
    response = await _send(client, token, thread_id, place["media_key"], duration_s=60)

    assert response.status_code == 422
    found = error(response)
    assert found["code"] == "AUDIO_TOO_LONG"
    assert found["details"] == {"max_seconds": 60}
    assert await _voice_notes(db, thread_id) == 0
    assert not [key for _, key in storage.objects if key.startswith("voice/")]


async def test_over_2_mb_is_refused_before_a_byte_is_read(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    storage = fake_providers.storage
    data = samples.webm(3000)
    place = await _upload(
        client, storage, token, thread_id, data + b"\x00" * (TWO_MB + 1 - len(data))
    )

    async def never(*_: Any) -> bytes:
        raise AssertionError("an upload over 2 MB was read")

    monkeypatch.setattr(storage, "get_bytes", never)
    response = await _send(client, token, thread_id, place["media_key"])

    assert response.status_code == 422
    found = error(response)
    assert found["code"] == "AUDIO_TOO_LARGE"
    assert found["details"] == {"max_bytes": TWO_MB}
    assert await _voice_notes(db, thread_id) == 0


async def test_a_file_grown_since_its_size_was_asked_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PUT again between the size and the read: the bytes read are what is
    kept, so their own size decides."""
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    storage = fake_providers.storage
    data = samples.webm(3000)
    place = await _upload(
        client, storage, token, thread_id, data + b"\x00" * (TWO_MB + 1 - len(data))
    )

    async def small(*_: Any) -> ObjectInfo:
        return ObjectInfo(size=len(data), content_type="audio/webm")

    monkeypatch.setattr(storage, "head", small)
    response = await _send(client, token, thread_id, place["media_key"])

    assert error(response)["code"] == "AUDIO_TOO_LARGE"
    assert await _voice_notes(db, thread_id) == 0


async def test_exactly_2_mb_is_judged_by_its_bytes(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    """At the limit, the size passes, and the bytes are read: padding after a
    WebM's last element is no element, so it is refused as unreadable."""
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    data = samples.webm(3000)
    place = await _upload(
        client,
        fake_providers.storage,
        token,
        thread_id,
        data + b"\x00" * (TWO_MB - len(data)),
    )

    response = await _send(client, token, thread_id, place["media_key"])

    assert error(response)["code"] == "UNSUPPORTED_AUDIO"


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (samples.ogg(3), "audio/webm"),  # signed for one, another arrived
        (samples.webm(3000), "audio/mp4"),
        (b"ID3\x04" + b"\x00" * 200, "audio/mp4"),  # an MP3
        (b"not audio at all", "audio/ogg"),
        (samples.webm(3000, doctype=b"matroska"), "audio/webm"),  # not WebM
        (samples.webm(3000, track_type=1), "audio/webm"),  # a video track
        (samples.mp4(3, handler=b"vide"), "audio/mp4"),
    ],
)
async def test_bytes_that_arent_the_signed_audio_are_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    data: bytes,
    content_type: str,
) -> None:
    _, _, _, token, thread = await _pair(make_user, make_thread)
    thread_id = thread.id
    place = await _upload(
        client, fake_providers.storage, token, thread_id, data, content_type
    )

    response = await _send(client, token, thread_id, place["media_key"])

    assert response.status_code == 422
    found = error(response)
    assert found["code"] == "UNSUPPORTED_AUDIO"
    assert found["details"] == {"accepted": ["audio/webm", "audio/ogg", "audio/mp4"]}
    assert await _voice_notes(db, thread_id) == 0


async def test_a_key_her_url_didnt_give_for_this_thread_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
) -> None:
    _, _, woman, token, thread = await _pair(make_user, make_thread)
    other_man, _ = await make_user()
    elsewhere = await make_thread(other_man, woman)
    thread_id = thread.id
    storage = fake_providers.storage
    theirs = await _upload(client, storage, token, elsewhere.id, samples.webm(3000))
    unsent = voice_upload_key(thread_id, uuid.uuid4(), "audio/webm")
    # A key of the server's own shape, with bytes there: still not an upload.
    await storage.put_bytes(
        PRIVATE,
        f"voice/{thread_id}/{uuid.uuid4()}.webm",
        samples.webm(3000),
        "audio/webm",
    )

    for key in (
        theirs["media_key"],  # another Thread's
        unsent,  # this Thread's shape, nothing uploaded
        f"voice/{thread_id}/{uuid.uuid4()}.webm",
        f"voice-uploads/{thread_id}/../{uuid.uuid4()}.webm",
        "raw/x",
    ):
        response = await _send(client, token, thread_id, key)
        assert response.status_code == 400, key
        found = error(response)
        assert found["code"] == "VALIDATION_ERROR"
        assert [f["field"] for f in found["details"]["fields"]] == ["media_key"]
    assert await _voice_notes(db, thread_id) == 0


async def test_a_thread_not_hers_is_not_found_before_storage_is_asked(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nobody learns from the answer whether another Thread holds an upload."""
    _, _, _, token, thread = await _pair(make_user, make_thread)
    _, outsider_token = await make_user(Gender.FEMALE)
    place = await _upload(
        client, fake_providers.storage, token, thread.id, samples.webm(3000)
    )

    async def never(*_: Any) -> Any:
        raise AssertionError("storage was asked for someone else's Thread")

    monkeypatch.setattr(fake_providers.storage, "head", never)
    response = await _send(client, outsider_token, thread.id, place["media_key"])

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "fields",
    [
        {"duration_s": 0},  # P-15: 1 to 60
        {"duration_s": 61},
        {"duration_s": -3},
        {"body": "Hello"},  # a voice note has no body
        {"media_key": None},
        {"media_key": "x" * 201},
    ],
)
async def test_a_malformed_voice_note_is_a_validation_error(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    fake_providers: FakeProviders,
    fields: dict[str, Any],
) -> None:
    _, _, _, token, thread = await _pair(make_user, make_thread)
    place = await _upload(
        client, fake_providers.storage, token, thread.id, samples.webm(3000)
    )

    fields = dict(fields)
    key = fields.pop("media_key", place["media_key"])
    response = await _send(client, token, thread.id, key, **fields)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
