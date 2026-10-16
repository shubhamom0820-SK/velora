"""`GET /v1/admin/moderation` and `POST /v1/admin/photos/{id}/decide` (T-9.5,
D-925): pending public and private photos, never a selfie or the face photo;
staff approve a pending photo, as the worker would, or take down a pending or
approved one. Either way a finished profile's completeness follows at once,
under the owner's row lock (P-210).
"""

from __future__ import annotations

import io
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import PhotoKind, ReviewStatus, Role
from app.core.providers import FakeProviders
from app.core.queue import BLUR_PHOTO, FakeQueue
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from tests.conftest import MakeUser
from tests.modules.admin.support import ADMIN, audits, auth, error, fresh, staff

pytestmark = pytest.mark.usefixtures("test_redis")

PUBLIC, PRIVATE = "velora-public", "velora-private"
NOTE = "Shows more than the rules allow."


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (800, 600), "teal").save(out, "JPEG")
    return out.getvalue()


async def _photo(
    db: AsyncSession,
    providers: FakeProviders,
    user_id: uuid.UUID,
    *,
    kind: PhotoKind = PhotoKind.PUBLIC,
    status: ReviewStatus = ReviewStatus.PENDING,
    position: int | None = 1,
    minutes_ago: int = 0,
    minor: float | None = None,
) -> uuid.UUID:
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user_id,
        kind=kind,
        position=position if kind is PhotoKind.PUBLIC else None,
        raw_key=f"raw/{user_id}/{photo_id}",
        status=status,
        moderation={"minor": minor} if minor is not None else None,
        created_at=clock.now() - timedelta(minutes=minutes_ago),
    )
    if status is ReviewStatus.APPROVED and kind is PhotoKind.PUBLIC:
        photo.public_key = f"p/{photo_id}.jpg"
        photo.blur_key = f"b/{uuid.uuid4()}.jpg"
        await providers.storage.put_bytes(
            PUBLIC, photo.public_key, b"pub", "image/jpeg"
        )
        await providers.storage.put_bytes(PUBLIC, photo.blur_key, b"blur", "image/jpeg")
    db.add(photo)
    await db.flush()
    await providers.storage.put_bytes(PRIVATE, photo.raw_key, _jpeg(), "image/jpeg")
    return photo_id


async def _decide(
    client: AsyncClient, token: str, photo_id: uuid.UUID, body: dict[str, object]
) -> Response:
    return await client.post(
        f"{ADMIN}/photos/{photo_id}/decide", json=body, headers=auth(token)
    )


async def _completeness(db: AsyncSession, user_id: uuid.UUID) -> int:
    value = await db.scalar(
        select(Profile.completeness)
        .where(Profile.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert value is not None
    return value


async def test_the_queue_is_pending_public_and_private_photos_oldest_first(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    woman_id = woman.id
    newer = await _photo(db, fake_providers, woman_id, minutes_ago=1, minor=0.12)
    older = await _photo(
        db, fake_providers, woman_id, kind=PhotoKind.PRIVATE, minutes_ago=9
    )
    for kind in (PhotoKind.SELFIE, PhotoKind.VERIFICATION):
        await _photo(
            db, fake_providers, woman_id, kind=kind, position=None, minutes_ago=30
        )
    await _photo(
        db,
        fake_providers,
        woman_id,
        status=ReviewStatus.APPROVED,
        position=0,
        minutes_ago=20,
    )

    response = await client.get(f"{ADMIN}/moderation", headers=auth(token))

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [(i["id"], i["kind"]) for i in items] == [
        (str(older), "private"),
        (str(newer), "public"),
    ]
    assert items[1]["minor_score"] == 0.12
    assert items[0]["url"].startswith(f"fake-storage://{PRIVATE}/raw/")
    [entry] = await audits(db, moderator_id, "moderation.list")
    assert entry.meta is None


async def test_approving_a_public_photo_publishes_it_and_lifts_completeness(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    woman_id = woman.id
    await _photo(db, fake_providers, woman_id, status=ReviewStatus.APPROVED, position=0)
    photo_id = await _photo(db, fake_providers, woman_id)

    response = await _decide(client, token, photo_id, {"approve": True})

    assert response.status_code == 204, response.text
    photo = await fresh(db, Photo, photo_id)
    assert photo.status is ReviewStatus.APPROVED
    assert photo.public_key == f"p/{photo_id}.jpg"
    assert (PUBLIC, photo.public_key) in fake_providers.storage.objects
    assert photo.moderation["staff"]["by"] == str(moderator_id)
    assert photo.moderation["staff"]["approved"] is True
    # Two approved public photos: 60 (make_user leaves it unset, 0, D-310).
    assert await _completeness(db, woman_id) == 60
    assert [job.job for job in fake_queue.jobs] == [BLUR_PHOTO]
    [entry] = await audits(db, moderator_id, "photo.decide")
    assert (entry.target_type, entry.target_id, entry.meta) == (
        "photo",
        photo_id,
        {"approve": True, "reason": None, "note": None},
    )


async def test_approving_a_private_photo_keeps_it_private(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    woman_id = woman.id
    photo_id = await _photo(db, fake_providers, woman_id, kind=PhotoKind.PRIVATE)

    response = await _decide(client, token, photo_id, {"approve": True})

    assert response.status_code == 204, response.text
    photo = await fresh(db, Photo, photo_id)
    assert (photo.status, photo.public_key) == (ReviewStatus.APPROVED, None)
    assert (
        PRIVATE,
        f"scored/{woman_id}/{photo_id}.jpg",
    ) in fake_providers.storage.objects
    assert not any(bucket == PUBLIC for bucket, _ in fake_providers.storage.objects)
    assert fake_queue.jobs == []


async def test_taking_down_an_approved_photo_removes_its_public_copies_and_keeps_the_record(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The 2-hour takedown (the founder, 16 October 2026): gone from the
    public bucket at once; the private copy and the row stay (rule 12)."""
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    woman_id = woman.id
    await _photo(db, fake_providers, woman_id, status=ReviewStatus.APPROVED, position=0)
    photo_id = await _photo(db, fake_providers, woman_id, status=ReviewStatus.APPROVED)
    photo = await fresh(db, Photo, photo_id)
    public_key, blur_key, raw = photo.public_key, photo.blur_key, photo.raw_key

    response = await _decide(
        client, token, photo_id, {"approve": False, "reason": "nudity", "note": NOTE}
    )

    assert response.status_code == 204, response.text
    photo = await fresh(db, Photo, photo_id)
    assert (photo.status, photo.reject_reason) == (ReviewStatus.REJECTED, "nudity")
    assert (PUBLIC, public_key) not in fake_providers.storage.objects
    assert (PUBLIC, blur_key) not in fake_providers.storage.objects
    assert (PRIVATE, raw) in fake_providers.storage.objects
    # One approved public photo left: 50.
    assert await _completeness(db, woman_id) == 50
    [entry] = await audits(db, moderator_id, "photo.decide")
    assert entry.meta == {"approve": False, "reason": "nudity", "note": NOTE}


@pytest.mark.parametrize("kind", [PhotoKind.SELFIE, PhotoKind.VERIFICATION])
async def test_a_selfie_or_the_face_photo_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    kind: PhotoKind,
) -> None:
    """D-264, D-925: they never reach the panel."""
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    photo_id = await _photo(db, fake_providers, woman.id, kind=kind, position=None)

    response = await _decide(
        client, token, photo_id, {"approve": False, "reason": "other", "note": NOTE}
    )

    assert response.status_code == 404
    assert (await fresh(db, Photo, photo_id)).status is ReviewStatus.PENDING
    assert await audits(db, moderator_id) == []


@pytest.mark.parametrize(
    ("status", "body", "why"),
    [
        (ReviewStatus.REJECTED, {"approve": True}, "rejected"),
        (
            ReviewStatus.REJECTED,
            {"approve": False, "reason": "other", "note": NOTE},
            "rejected",
        ),
        (ReviewStatus.APPROVED, {"approve": True}, "approved"),
    ],
    ids=["approve a rejected", "reject a rejected", "approve an approved"],
)
async def test_a_decided_photo_is_not_decided_again(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    status: ReviewStatus,
    body: dict[str, object],
    why: str,
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    photo_id = await _photo(db, fake_providers, woman.id, status=status)

    response = await _decide(client, token, photo_id, body)

    assert response.status_code == 422
    assert error(response)["details"]["why"] == why
    assert (await fresh(db, Photo, photo_id)).status is status
    assert await audits(db, moderator_id) == []


@pytest.mark.parametrize(
    "body",
    [
        {"approve": False, "note": NOTE},
        {"approve": False, "reason": "nudity"},
        {"approve": False, "reason": "nudity", "note": "short"},
        {"approve": True, "reason": "nudity"},
        {"approve": True, "note": NOTE},
        {"approve": False, "reason": "minor_suspected", "note": NOTE},
        {"approve": False, "reason": "no_face", "note": NOTE},
    ],
    ids=[
        "a rejection with no reason",
        "a rejection with no note",
        "a short note",
        "an approval with a reason",
        "an approval with a note",
        "the model's minor",
        "no_face",
    ],
)
async def test_a_decision_out_of_shape_is_a_validation_error(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    body: dict[str, object],
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)
    woman, _ = await make_user("female")
    photo_id = await _photo(db, fake_providers, woman.id)

    response = await _decide(client, token, photo_id, body)

    assert response.status_code == 400, response.text
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert (await fresh(db, Photo, photo_id)).status is ReviewStatus.PENDING


async def test_an_unknown_photo_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await staff(make_user, Role.MODERATOR)

    response = await _decide(client, token, uuid.uuid4(), {"approve": True})

    assert response.status_code == 404
