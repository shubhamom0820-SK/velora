"""`POST /v1/photos/upload-url` and `POST /v1/photos/{id}/complete` (T-4.2).

The browser uploads to the presigned URL itself, so a test puts the bytes in the
fake storage where the URL points, as the browser would, then completes.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers import FakeProviders
from app.core.queue import MODERATE_PHOTO, FakeQueue
from app.modules.photos import service
from app.modules.photos.models import Photo
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.images import GIF, HEIC, HTML, JPEG, PNG, WEBP

pytestmark = pytest.mark.usefixtures("test_redis")

PRIVATE = "velora-private"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return error


async def _at(
    db: AsyncSession, make_user: MakeUser, step: OnboardingStep = OnboardingStep.PHOTOS
) -> tuple[User, str]:
    user, token = await make_user(onboarded=False)
    user.onboarding_step = step
    await db.flush()
    return user, token


async def _upload_url(
    client: AsyncClient,
    token: str,
    kind: str = "public",
    position: int | None = 0,
    content_type: str = "image/jpeg",
) -> Response:
    body: dict[str, Any] = {"kind": kind, "content_type": content_type}
    if position is not None:
        body["position"] = position
    return await client.post("/v1/photos/upload-url", json=body, headers=_bearer(token))


async def _photo(db: AsyncSession, photo_id: str) -> Photo:
    photo = await db.scalar(select(Photo).where(Photo.id == uuid.UUID(photo_id)))
    assert photo is not None
    await db.refresh(photo)
    return photo


async def _uploaded(
    client: AsyncClient,
    db: AsyncSession,
    fake_providers: FakeProviders,
    token: str,
    data: bytes,
    *,
    kind: str = "public",
    position: int | None = 0,
    declared: str = "image/jpeg",
) -> str:
    """Ask for a URL, then put `data` where it points, as the browser would."""
    response = await _upload_url(client, token, kind, position, declared)
    assert response.status_code == 200, response.text
    photo_id: str = response.json()["photo_id"]
    photo = await _photo(db, photo_id)
    await fake_providers.storage.put_bytes(PRIVATE, photo.raw_key, data, declared)
    return photo_id


async def _complete(client: AsyncClient, token: str, photo_id: str) -> Response:
    return await client.post(f"/v1/photos/{photo_id}/complete", headers=_bearer(token))


# --- The upload URL -----------------------------------------------------------------


async def test_a_url_to_upload_one_photo_to_the_private_bucket(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await _at(db, make_user)

    response = await _upload_url(client, token, content_type="image/png")

    assert response.status_code == 200
    body = response.json()
    photo = await _photo(db, body["photo_id"])
    assert photo.raw_key == f"raw/{user.id}/{photo.id}"
    assert (photo.kind, photo.position, photo.status) == (
        PhotoKind.PUBLIC,
        0,
        ReviewStatus.PENDING,
    )
    assert body["put_url"].startswith(
        f"fake-storage://{PRIVATE}/{photo.raw_key}?method=PUT"
    )
    assert "ttl=300" in body["put_url"]
    assert body["headers"] == {"Content-Type": "image/png"}


@pytest.mark.parametrize("declared", ["image/heic", "image/gif", "text/html", ""])
async def test_a_declared_type_we_refuse_anyway_is_refused_saying_what_to_do(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, declared: str
) -> None:
    _, token = await _at(db, make_user)

    response = await _upload_url(client, token, content_type=declared)

    assert response.status_code == 422
    error = _error(response)
    assert error["code"] == "UNSUPPORTED_IMAGE"
    assert "JPEG, PNG or WebP" in error["message"]
    assert await db.scalar(select(Photo.id)) is None


async def test_before_the_photos_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _upload_url(client, token)

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(response)["details"] == {"step": "about"}


async def test_after_the_photos_step_a_photo_is_an_edit(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user, OnboardingStep.INTERESTS)

    assert (await _upload_url(client, token)).status_code == 200


async def test_a_selfie_waits_for_its_own_step(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, early = await _at(db, make_user, OnboardingStep.PIN)
    _, ready = await _at(db, make_user, OnboardingStep.SELFIE)

    refused = await _upload_url(client, early, kind="selfie", position=None)
    allowed = await _upload_url(client, ready, kind="selfie", position=None)

    assert _error(refused)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(refused)["details"] == {"step": "pin"}
    assert allowed.status_code == 200


@pytest.mark.parametrize(
    ("kind", "position", "field"),
    [
        ("public", None, "position"),
        ("private", 0, "position"),
        ("selfie", 1, "position"),
    ],
)
async def test_a_position_only_where_it_belongs(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    kind: str,
    position: int | None,
    field: str,
) -> None:
    _, token = await _at(db, make_user, OnboardingStep.SELFIE)

    response = await _upload_url(client, token, kind=kind, position=position)

    assert response.status_code == 400
    assert _error(response)["details"]["fields"][0]["field"] == field


@pytest.mark.parametrize("position", [-1, 6])
async def test_public_places_are_zero_to_five(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, position: int
) -> None:
    _, token = await _at(db, make_user)

    response = await _upload_url(client, token, position=position)

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"


async def test_a_public_place_holds_one_photo(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user)
    assert (await _upload_url(client, token, position=2)).status_code == 200

    response = await _upload_url(client, token, position=2)

    assert response.status_code == 422
    assert (_error(response)["code"], _error(response)["details"]) == (
        "NOT_ALLOWED",
        {"position": 2},
    )


async def test_six_private_photos_and_no_more(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user)
    for _ in range(6):
        ok = await _upload_url(client, token, kind="private", position=None)
        assert ok.status_code == 200

    seventh = await _upload_url(client, token, kind="private", position=None)

    assert seventh.status_code == 422
    assert _error(seventh)["code"] == "NOT_ALLOWED"


async def test_one_selfie_waits_at_a_time(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user, OnboardingStep.SELFIE)
    assert (
        await _upload_url(client, token, kind="selfie", position=None)
    ).status_code == 200

    second = await _upload_url(client, token, kind="selfie", position=None)

    assert _error(second)["code"] == "NOT_ALLOWED"


async def _age(db: AsyncSession, photo_id: str, by: timedelta) -> None:
    await db.execute(
        update(Photo)
        .where(Photo.id == uuid.UUID(photo_id))
        .values(created_at=clock.now() - by)
    )


async def test_an_abandoned_upload_frees_its_place(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Its URL expired and nothing ever arrived: the place is free again, and
    the old row says why it went."""
    _, token = await _at(db, make_user)
    first = (await _upload_url(client, token, position=0)).json()["photo_id"]
    await _age(db, first, service.ABANDONED_AFTER + timedelta(seconds=1))

    again = await _upload_url(client, token, position=0)

    assert again.status_code == 200
    old = await _photo(db, first)
    assert (old.status, old.reject_reason) == (ReviewStatus.REJECTED, "abandoned")


async def test_an_upload_that_arrived_isnt_abandoned(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    _, token = await _at(db, make_user)
    first = await _uploaded(client, db, fake_providers, token, JPEG, position=0)
    await _age(db, first, service.ABANDONED_AFTER + timedelta(seconds=1))

    again = await _upload_url(client, token, position=0)

    assert _error(again)["code"] == "NOT_ALLOWED"
    assert (await _photo(db, first)).status is ReviewStatus.PENDING


async def test_an_upload_whose_url_hasnt_expired_isnt_abandoned(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user)
    first = (await _upload_url(client, token, position=0)).json()["photo_id"]
    await _age(db, first, service.ABANDONED_AFTER - timedelta(seconds=30))

    again = await _upload_url(client, token, position=0)

    assert _error(again)["code"] == "NOT_ALLOWED"


async def test_thirty_upload_urls_an_hour(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user)
    for _ in range(30):
        await _upload_url(client, token, kind="private", position=None)

    response = await _upload_url(client, token, kind="private", position=None)

    assert response.status_code == 429
    assert _error(response)["code"] == "RATE_LIMITED"


async def test_signed_out_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.post(
        "/v1/photos/upload-url",
        json={"kind": "public", "position": 0, "content_type": "image/jpeg"},
    )

    assert _error(response)["code"] == "AUTH_REQUIRED"


# --- Complete: the bytes decide (D-089) ---------------------------------------------


@pytest.mark.parametrize(
    ("data", "declared", "judged"),
    [
        (JPEG, "image/jpeg", "image/jpeg"),
        (PNG, "image/png", "image/png"),
        (WEBP, "image/webp", "image/webp"),
        # Declared one way, the bytes another: handled by its bytes.
        (PNG, "image/jpeg", "image/png"),
        (JPEG, "image/webp", "image/jpeg"),
    ],
    ids=["jpeg", "png", "webp", "png-declared-jpeg", "jpeg-declared-webp"],
)
async def test_a_photo_goes_to_moderation_as_its_bytes_say(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    data: bytes,
    declared: str,
    judged: str,
) -> None:
    _, token = await _at(db, make_user)
    photo_id = await _uploaded(
        client, db, fake_providers, token, data, declared=declared
    )

    response = await _complete(client, token, photo_id)

    assert response.status_code == 200
    assert response.json() == {
        "id": photo_id,
        "kind": "public",
        "position": 0,
        "status": "pending",
        "reject_reason": None,
    }
    [job] = fake_queue.named(MODERATE_PHOTO)
    assert job.kwargs == {"photo_id": photo_id, "image_type": judged}
    assert job.job_id == f"moderate_photo:{photo_id}"


@pytest.mark.parametrize(
    "data", [HEIC, GIF, HTML, b""], ids=["heic", "gif", "html", "empty"]
)
async def test_bytes_that_arent_one_of_the_three_are_refused_whatever_they_claim(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
    data: bytes,
) -> None:
    _, token = await _at(db, make_user)
    photo_id = await _uploaded(
        client, db, fake_providers, token, data, declared="image/jpeg"
    )
    raw_key = (await _photo(db, photo_id)).raw_key

    response = await _complete(client, token, photo_id)

    assert response.status_code == 422
    error = _error(response)
    assert error["code"] == "UNSUPPORTED_IMAGE"
    assert "JPEG, PNG or WebP" in error["message"]
    photo = await _photo(db, photo_id)
    assert (photo.status, photo.reject_reason) == (
        ReviewStatus.REJECTED,
        "unsupported_format",
    )
    assert (PRIVATE, raw_key) not in fake_providers.storage.objects
    assert fake_queue.jobs == []


async def test_over_eight_megabytes_is_refused_and_removed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    _, token = await _at(db, make_user)
    big = JPEG + b"\x00" * (service.MAX_UPLOAD_BYTES + 1 - len(JPEG))
    photo_id = await _uploaded(client, db, fake_providers, token, big)
    exactly = await _uploaded(
        client,
        db,
        fake_providers,
        token,
        JPEG + b"\x00" * (service.MAX_UPLOAD_BYTES - len(JPEG)),
        position=1,
    )

    refused = await _complete(client, token, photo_id)
    accepted = await _complete(client, token, exactly)

    assert _error(refused)["code"] == "IMAGE_TOO_LARGE"
    assert (await _photo(db, photo_id)).reject_reason == "too_large"
    assert accepted.status_code == 200
    assert [job.kwargs["photo_id"] for job in fake_queue.jobs] == [exactly]


async def test_complete_before_uploading_changes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, fake_queue: FakeQueue
) -> None:
    _, token = await _at(db, make_user)
    photo_id = (await _upload_url(client, token)).json()["photo_id"]

    response = await _complete(client, token, photo_id)

    assert response.status_code == 422
    assert _error(response)["code"] == "NOT_ALLOWED"
    assert (await _photo(db, photo_id)).status is ReviewStatus.PENDING
    assert fake_queue.jobs == []


async def test_someone_elses_photo_is_not_found_as_if_it_didnt_exist(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    _, owner = await _at(db, make_user)
    _, other = await _at(db, make_user)
    photo_id = await _uploaded(client, db, fake_providers, owner, JPEG)

    theirs = await _complete(client, other, photo_id)
    nobodys = await _complete(client, other, str(uuid.uuid4()))

    assert theirs.status_code == nobodys.status_code == 404
    assert theirs.json() == nobodys.json()


async def test_saying_done_twice_queues_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    _, token = await _at(db, make_user)
    photo_id = await _uploaded(client, db, fake_providers, token, JPEG)

    first = await _complete(client, token, photo_id)
    second = await _complete(client, token, photo_id)

    assert first.json() == second.json()
    assert len(fake_queue.named(MODERATE_PHOTO)) == 1


async def test_a_rejected_photo_stays_rejected(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    _, token = await _at(db, make_user)
    photo_id = await _uploaded(client, db, fake_providers, token, HEIC)
    await _complete(client, token, photo_id)

    again = await _complete(client, token, photo_id)

    assert again.status_code == 200
    assert (again.json()["status"], again.json()["reject_reason"]) == (
        "rejected",
        "unsupported_format",
    )
    assert fake_queue.jobs == []


async def test_a_selfie_waits_for_its_submit(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    """Nothing queued: T-4.5's submit queues `verify_selfie`."""
    _, token = await _at(db, make_user, OnboardingStep.SELFIE)
    photo_id = await _uploaded(
        client, db, fake_providers, token, JPEG, kind="selfie", position=None
    )

    response = await _complete(client, token, photo_id)

    assert response.json()["status"] == "pending"
    assert fake_queue.jobs == []


async def test_a_queue_that_refuses_leaves_the_photo_to_complete_again(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    _, token = await _at(db, make_user)
    photo_id = await _uploaded(client, db, fake_providers, token, JPEG)
    fake_queue.fail = True

    failed = await _complete(client, token, photo_id)
    retried = await _complete(client, token, photo_id)

    assert failed.status_code == 500
    assert (await _photo(db, photo_id)).status is ReviewStatus.PENDING
    assert retried.status_code == 200
    assert len(fake_queue.named(MODERATE_PHOTO)) == 1
