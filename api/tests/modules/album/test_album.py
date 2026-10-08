"""The album itself (T-8.4): `GET /v1/users/{id}/album` and the copies the
`watermark_album` job keeps (`album.service.sync_copies`).

What he sees is only ever his own copies, each rendered from the photo's
scored copy (D-700), never its upload, with his `@username` over it; the
upload here holds other bytes, so a copy made from it would show. A copy is
recorded only while the request is granted, and deleted, file then row, once
it isn't or the photo is gone. A private photo approved before D-700 wrote
scored copies has none, so it is never shown (beta: it stays out until its
owner uploads it again)."""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from PIL import Image, ImageChops, ImageStat
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import images
from app.core.enums import AlbumRequestStatus, Gender
from app.core.providers import FakeProviders
from app.core.providers.storage import FakeStorage
from app.core.queue import WATERMARK_ALBUM, FakeQueue
from app.core.storage_keys import album_key
from app.modules.album import repository as album_repository
from app.modules.album import service as album_service
from app.modules.album.models import AlbumRequest
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.album.support import (
    PRIVATE,
    SETTINGS,
    album_of,
    approved_without_score,
    asked,
    copies_of,
    decide,
    revoke,
    view,
)
from tests.modules.discovery.support import bearer, block, error
from tests.modules.gifts.support import token_for
from tests.modules.photos.test_moderate import Sessions

pytestmark = pytest.mark.usefixtures("test_redis")


def _ok(response: Response) -> Any:
    assert response.status_code == 200, response.text
    return response.json()


def _keys(album: Any) -> list[str]:
    """The key each link is signed for, read back from the fake's URL."""
    prefix = f"fake-storage://{PRIVATE}/"
    keys = []
    for photo in album["photos"]:
        url = photo["url"]
        assert url.startswith(prefix) and url.endswith("?method=GET&ttl=600"), url
        keys.append(url.removeprefix(prefix).removesuffix("?method=GET&ttl=600"))
    return keys


def _pixels(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
        return image.convert("RGB")


def _difference(a: bytes, b: bytes) -> float:
    return sum(ImageStat.Stat(ImageChops.difference(_pixels(a), _pixels(b))).mean)


async def _sync(
    db: AsyncSession, storage: FakeStorage, request_id: str | uuid.UUID
) -> str:
    return await album_service.sync_copies(
        Sessions(db),
        uuid.UUID(str(request_id)),
        storage=storage,
        settings=SETTINGS,
    )


async def _granted(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    storage: FakeStorage,
    *,
    photos: int = 2,
) -> tuple[User, str, User, str, str]:
    """A woman's album of `photos`, and a man she granted it to: (him, his
    token, her, her token, the request's id)."""
    man, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    await album_of(db, woman, storage, photos=photos)
    request = await asked(client, token, woman.id)
    assert (await decide(client, woman_token, request["id"], True)).status_code == 200
    return man, token, woman, woman_token, request["id"]


# --- What he sees ------------------------------------------------------------------------


async def test_before_a_grant_he_sees_his_requests_status_and_no_photo(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _man, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    woman_id = woman.id
    await album_of(db, woman)

    assert _ok(await view(client, token, woman_id)) == {"status": None, "photos": []}
    request = await asked(client, token, woman_id)
    assert _ok(await view(client, token, woman_id)) == {
        "status": "pending",
        "photos": [],
    }
    await decide(client, woman_token, request["id"], False)
    assert _ok(await view(client, token, woman_id)) == {
        "status": "declined",
        "photos": [],
    }


@pytest.mark.critical
async def test_granted_he_sees_his_own_copies_made_from_the_scored_bytes(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """06-TESTING's critical 14 for the album: never the upload (D-700), never
    another viewer's copy, never the scored copy itself."""
    storage = fake_providers.storage
    man, token, woman, _, request_id = await _granted(db, client, make_user, storage)
    woman_id = woman.id
    _other, other_token = await make_user(credits=3)
    other_request = await asked(client, other_token, woman_id)
    await decide(client, token_for(woman_id), other_request["id"], True)

    assert await _sync(db, storage, request_id) == "made 2, deleted 0"
    assert await _sync(db, storage, other_request["id"]) == "made 2, deleted 0"
    album = _ok(await view(client, token, woman_id))

    copies = await copies_of(db, uuid.UUID(request_id))
    photos = await _photos_of(db, woman_id)
    assert album["status"] == "granted"
    assert _keys(album) == [
        album_key(uuid.UUID(request_id), photo.id) for photo in photos
    ]
    assert sorted(c.file_key for c in copies) == sorted(_keys(album))
    assert {(c.owner_id, c.viewer_id) for c in copies} == {(woman_id, man.id)}
    for photo, key in zip(photos, _keys(album), strict=True):
        assert photo.scored_key is not None
        copy = storage.objects[(PRIVATE, key)].data
        scored = storage.objects[(PRIVATE, photo.scored_key)].data
        upload = storage.objects[(PRIVATE, photo.raw_key)].data
        assert 0 < _difference(copy, scored) < _difference(copy, upload)
        assert storage.objects[(PRIVATE, key)].content_type == "image/jpeg"
    others = _keys(_ok(await view(client, other_token, woman_id)))
    assert set(others).isdisjoint(_keys(album))
    assert "raw/" not in str(album) and "scored/" not in str(album)


async def _photos_of(db: AsyncSession, owner_id: uuid.UUID) -> list[Photo]:
    return await album_repository.albumable_photos(db, owner_id)


async def test_the_copy_carries_his_username(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = fake_providers.storage
    man, _, _, _, request_id = await _granted(db, client, make_user, storage, photos=1)
    username = (await db.get(Profile, man.id)).username  # type: ignore[union-attr]
    written: list[str] = []
    real = images.watermark

    def watermark(data: bytes, text: str) -> bytes:
        written.append(text)
        return real(data, text)

    monkeypatch.setattr(images, "watermark", watermark)

    await _sync(db, storage, request_id)

    assert written == [f"@{username}"]


async def test_a_photo_approved_before_scored_copies_is_never_shown(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """P-79, D-700: it has no scored copy, and the album never reads an
    upload, so it has no copy either. Beta: accepted, until re-uploaded."""
    storage = fake_providers.storage
    _, token, woman, _, request_id = await _granted(
        db, client, make_user, storage, photos=1
    )
    woman_id = woman.id
    old = await approved_without_score(db, woman)

    await _sync(db, storage, request_id)
    album = _ok(await view(client, token, woman_id))

    assert len(album["photos"]) == 1
    assert old.id not in {
        c.photo_id for c in await copies_of(db, uuid.UUID(request_id))
    }
    assert not any(str(old.id) in key for _, key in storage.objects)


async def test_a_photo_added_after_the_grant_is_queued_then_shown(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    storage = fake_providers.storage
    _, token, woman, _, request_id = await _granted(
        db, client, make_user, storage, photos=1
    )
    woman_id = woman.id
    await _sync(db, storage, request_id)
    [new] = await album_of(db, woman, storage, photos=1)

    assert len(_ok(await view(client, token, woman_id))["photos"]) == 1
    assert [(j.job_id, j.kwargs) for j in fake_queue.named(WATERMARK_ALBUM)][-1] == (
        f"watermark_album:{request_id}:{new.id}",
        {"request_id": request_id},
    )

    assert await _sync(db, storage, request_id) == "made 1, deleted 0"
    assert len(_ok(await view(client, token, woman_id))["photos"]) == 2


async def test_a_photo_she_removes_leaves_every_album_file_and_row(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    storage = fake_providers.storage
    _, token, woman, woman_token, request_id = await _granted(
        db, client, make_user, storage
    )
    woman_id = woman.id
    await _sync(db, storage, request_id)
    gone, kept = await _photos_of(db, woman_id)
    gone_key = album_key(uuid.UUID(request_id), gone.id)

    response = await client.delete(f"/v1/photos/{gone.id}", headers=bearer(woman_token))

    assert response.status_code == 204, response.text
    # Out of the album at once, before the job has run.
    assert _keys(_ok(await view(client, token, woman_id))) == [
        album_key(uuid.UUID(request_id), kept.id)
    ]
    assert (f"watermark_album:{request_id}:{gone.id}", {"request_id": request_id}) in [
        (j.job_id, j.kwargs) for j in fake_queue.named(WATERMARK_ALBUM)
    ]
    assert await _sync(db, storage, request_id) == "made 0, deleted 1"
    assert (PRIVATE, gone_key) not in storage.objects
    assert [c.photo_id for c in await copies_of(db, uuid.UUID(request_id))] == [kept.id]


async def test_a_revoke_leaves_him_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    storage = fake_providers.storage
    _, token, woman, woman_token, request_id = await _granted(
        db, client, make_user, storage
    )
    woman_id = woman.id
    await _sync(db, storage, request_id)
    files = [c.file_key for c in await copies_of(db, uuid.UUID(request_id))]
    assert len(files) == 2

    assert (await revoke(client, woman_token, request_id)).status_code == 204
    assert _ok(await view(client, token, woman_id)) == {
        "status": "revoked",
        "photos": [],
    }
    assert await _sync(db, storage, request_id) == "deleted 2"

    assert await copies_of(db, uuid.UUID(request_id)) == []
    assert not any((PRIVATE, key) in storage.objects for key in files)


async def test_a_copy_rendered_as_she_revokes_is_deleted_never_kept(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The revoke lands while the copy is being written: the job finds the
    request no longer granted under its lock, and deletes the file it wrote."""
    storage = fake_providers.storage
    _, _, _, _, request_id = await _granted(db, client, make_user, storage, photos=1)
    real_put = storage.put_bytes

    async def put_then_revoke(bucket: str, key: str, data: bytes, kind: str) -> None:
        await real_put(bucket, key, data, kind)
        await db.execute(
            update(AlbumRequest)
            .where(AlbumRequest.id == uuid.UUID(request_id))
            .values(status=AlbumRequestStatus.REVOKED)
        )

    monkeypatch.setattr(storage, "put_bytes", put_then_revoke)

    assert await _sync(db, storage, request_id) == "made 0, deleted 0"

    assert await copies_of(db, uuid.UUID(request_id)) == []
    assert not any(key.startswith("album/") for _, key in storage.objects)


async def test_storage_failing_is_tried_again(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = fake_providers.storage
    _, _, _, _, request_id = await _granted(db, client, make_user, storage, photos=1)

    async def down(*_: Any) -> bytes:
        raise ConnectionError("storage is down")

    monkeypatch.setattr(storage, "get_bytes", down)

    with pytest.raises(album_service.TryAgain):
        await _sync(db, storage, request_id)
    assert await copies_of(db, uuid.UUID(request_id)) == []


# --- Who may look --------------------------------------------------------------------------


async def test_after_a_block_either_way_the_album_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    storage = fake_providers.storage
    man, token, woman, _, request_id = await _granted(db, client, make_user, storage)
    man_id, woman_id = man.id, woman.id
    await _sync(db, storage, request_id)
    expected = error(await view(client, token, uuid.uuid4()))
    assert _ok(await view(client, token, woman_id))["status"] == "granted"

    her, him = await db.get(User, woman_id), await db.get(User, man_id)
    assert her is not None and him is not None
    await block(db, her, him)

    assert error(await view(client, token, woman_id)) == expected
    assert error(await view(client, token, man_id)) == expected
    assert expected["code"] == "NOT_FOUND"
