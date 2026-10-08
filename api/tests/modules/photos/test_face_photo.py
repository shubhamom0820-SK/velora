"""The face photo through the API (T-4.12, D-391): uploaded as kind
`verification` at the `photos` step, one live per person, replaced by the next
until the selfie matched or is being compared; listed to its owner alone; and
`POST /v1/photos/{id}/show`, the toggle that also shows it on the profile as an
ordinary public photo through the ordinary pipeline."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers import FakeProviders
from app.core.queue import MATCH_PHOTO, MODERATE_PHOTO, FakeQueue
from app.modules.photos import service
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification.models import Verification
from tests.conftest import MakeUser, make_test_settings
from tests.images import JPEG
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import jpeg

pytestmark = pytest.mark.usefixtures("test_redis")

PUBLIC, PRIVATE = "velora-public", "velora-private"


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


async def _upload_url(client: AsyncClient, token: str, **body: Any) -> Response:
    return await client.post(
        "/v1/photos/upload-url",
        json={"kind": "verification", "content_type": "image/jpeg", **body},
        headers=_bearer(token),
    )


async def _face(
    db: AsyncSession,
    fake_providers: FakeProviders,
    user: User,
    *,
    status: ReviewStatus = ReviewStatus.APPROVED,
    data: bytes = JPEG,
) -> Photo:
    """A face photo as moderation leaves one: its private copy the scored
    bytes, a record with a face, no public copy."""
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=PhotoKind.VERIFICATION,
        raw_key=f"raw/{user.id}/{photo_id}",
        status=status,
        moderation={"provider": "sightengine", "faces": 1},
    )
    db.add(photo)
    await db.flush()
    await fake_providers.storage.put_bytes(PRIVATE, photo.raw_key, data, "image/jpeg")
    return photo


async def _public(
    db: AsyncSession, fake_providers: FakeProviders, user: User, position: int
) -> Photo:
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=PhotoKind.PUBLIC,
        position=position,
        raw_key=f"raw/{user.id}/{photo_id}",
        public_key=f"p/{photo_id}.jpg",
        status=ReviewStatus.APPROVED,
    )
    db.add(photo)
    await db.flush()
    return photo


async def _matched(
    db: AsyncSession, user: User, fake_providers: FakeProviders | None = None
) -> None:
    """The selfie matched: `is_verified`, the approved verification and its
    selfie, its file in the private bucket when `fake_providers` is given."""
    selfie_id = uuid.uuid4()
    raw = f"raw/{user.id}/{selfie_id}"
    db.add(
        Photo(
            id=selfie_id,
            user_id=user.id,
            kind=PhotoKind.SELFIE,
            raw_key=raw,
            status=ReviewStatus.APPROVED,
        )
    )
    await db.flush()
    if fake_providers is not None:
        await fake_providers.storage.put_bytes(
            PRIVATE, raw, jpeg("salmon"), "image/jpeg"
        )
    db.add(
        Verification(
            user_id=user.id,
            challenge="none",
            selfie_photo_id=selfie_id,
            status=ReviewStatus.APPROVED,
        )
    )
    user.is_verified = True
    await db.flush()


async def _fresh(db: AsyncSession, photo_id: uuid.UUID) -> Photo:
    found = await db.scalar(
        select(Photo)
        .where(Photo.id == photo_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _show(client: AsyncClient, token: str, photo_id: Any) -> Response:
    return await client.post(f"/v1/photos/{photo_id}/show", headers=_bearer(token))


# --- Uploading it --------------------------------------------------------------------


async def test_a_face_photo_is_uploaded_at_the_photos_step_with_no_place(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user)

    response = await _upload_url(client, token)

    assert response.status_code == 200, response.text
    photo = await _fresh(db, uuid.UUID(response.json()["photo_id"]))
    assert (photo.kind, photo.position, photo.status) == (
        PhotoKind.VERIFICATION,
        None,
        ReviewStatus.PENDING,
    )
    assert response.json()["put_url"].startswith(f"fake-storage://{PRIVATE}/")


async def test_a_place_is_refused_for_a_face_photo(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user)

    response = await _upload_url(client, token, position=0)

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    assert _error(response)["details"]["fields"] == [
        {"field": "position", "problem": "is only for public photos"}
    ]


async def test_before_the_photos_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _upload_url(client, token)

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"


@pytest.mark.parametrize(
    "status", [ReviewStatus.PENDING, ReviewStatus.APPROVED], ids=["pending", "approved"]
)
async def test_one_live_face_photo_a_new_one_replaces_the_old(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    status: ReviewStatus,
) -> None:
    """No match rests on the old one, so it is `replaced`, its file deleted
    after the commit (the selfie's rule, D-263), and nothing else of hers is
    touched."""
    user, token = await _at(db, make_user)
    old = await _face(db, fake_providers, user, status=status)
    kept = await _public(db, fake_providers, user, 0)

    response = await _upload_url(client, token)

    assert response.status_code == 200, response.text
    replaced = await _fresh(db, old.id)
    assert (replaced.status, replaced.reject_reason) == (
        ReviewStatus.REJECTED,
        "replaced",
    )
    assert (PRIVATE, old.raw_key) not in fake_providers.storage.objects
    assert (await _fresh(db, kept.id)).status is ReviewStatus.APPROVED
    live = await db.scalars(
        select(Photo.id).where(
            Photo.user_id == user.id,
            Photo.kind == PhotoKind.VERIFICATION,
            Photo.status != ReviewStatus.REJECTED,
        )
    )
    assert [str(i) for i in live] == [response.json()["photo_id"]]


async def test_the_face_photo_cant_change_once_the_selfie_matched(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """T-4.12's plan, point 4: the match can't be left pointing at a photo
    that is gone; a change then goes through P-163's path."""
    user, token = await _at(db, make_user, OnboardingStep.DONE)
    face = await _face(db, fake_providers, user)
    face_id, raw_key = face.id, face.raw_key  # a refused request expires `face`
    await _matched(db, user)

    response = await _upload_url(client, token)

    assert response.status_code == 422
    assert _error(response) == {
        "code": "NOT_ALLOWED",
        "message": "Your face photo can't change once your selfie matched.",
    }
    assert (await _fresh(db, face_id)).status is ReviewStatus.APPROVED
    assert (PRIVATE, raw_key) in fake_providers.storage.objects


async def test_nor_while_a_selfie_is_being_compared_with_it(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user, OnboardingStep.SELFIE)
    face = await _face(db, fake_providers, user)
    selfie_id = uuid.uuid4()
    db.add(
        Photo(
            id=selfie_id,
            user_id=user.id,
            kind=PhotoKind.SELFIE,
            raw_key=f"raw/{user.id}/{selfie_id}",
        )
    )
    await db.flush()
    db.add(Verification(user_id=user.id, challenge="none", selfie_photo_id=selfie_id))
    await db.flush()
    face_id = face.id

    response = await _upload_url(client, token)

    assert response.status_code == 422
    assert _error(response)["message"] == (
        "Your face photo can't change while your selfie is compared."
    )
    assert (await _fresh(db, face_id)).status is ReviewStatus.APPROVED


# --- Who sees it ---------------------------------------------------------------------


@pytest.mark.critical
async def test_the_face_photo_is_its_owners_alone(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """06-TESTING #14, extended: listed to its owner by a signed link to the
    private bucket, never at the CDN; to anyone else, `GET /photos/{id}` is
    the same `NOT_FOUND` as no photo, and `GET /me/photos` doesn't list it."""
    user, token = await _at(db, make_user)
    _, other = await _at(db, make_user)
    face = await _face(db, fake_providers, user)

    mine = await client.get("/v1/me/photos", headers=_bearer(token))
    assert [p["kind"] for p in mine.json()] == ["verification"]
    assert mine.json()[0]["url"] == (
        f"fake-storage://{PRIVATE}/{face.raw_key}?method=GET&ttl=600"
    )
    assert (
        await client.get(f"/v1/photos/{face.id}", headers=_bearer(token))
    ).status_code == 200

    theirs = await client.get("/v1/me/photos", headers=_bearer(other))
    assert theirs.json() == []
    one = await client.get(f"/v1/photos/{face.id}", headers=_bearer(other))
    none = await client.get(f"/v1/photos/{uuid.uuid4()}", headers=_bearer(other))
    assert (one.status_code, one.json()) == (404, none.json())
    assert [
        key for bucket, key in fake_providers.storage.objects if bucket == PUBLIC
    ] == []


# --- Showing it on the profile (the toggle) --------------------------------------------


async def test_show_makes_a_pending_public_copy_and_sends_it_through_moderation(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    """An ordinary public photo in the first free place, from the face photo's
    private copy, pending, queued as any upload is: never approved at once,
    since a presigned PUT outlives `complete` by up to five minutes (P-79) and
    a public copy is only ever made from scored bytes (T-4.4). It carries
    `from_photo_id`; the face photo itself is untouched."""
    user, token = await _at(db, make_user)
    await _public(db, fake_providers, user, 0)
    await _public(db, fake_providers, user, 2)
    face = await _face(db, fake_providers, user, data=JPEG)

    response = await _show(client, token, face.id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["kind"], body["position"], body["status"], body["from_photo_id"]) == (
        "public",
        1,
        "pending",
        str(face.id),
    )
    copy = await _fresh(db, uuid.UUID(body["id"]))
    assert copy.public_key is None
    assert copy.raw_key != face.raw_key
    assert fake_providers.storage.objects[(PRIVATE, copy.raw_key)].data == JPEG
    assert [
        key for bucket, key in fake_providers.storage.objects if bucket == PUBLIC
    ] == []
    [job] = fake_queue.named(MODERATE_PHOTO)
    assert (job.job_id, job.kwargs) == (
        f"moderate_photo:{copy.id}",
        {"photo_id": str(copy.id), "image_type": "image/jpeg"},
    )
    assert (await _fresh(db, face.id)).status is ReviewStatus.APPROVED


async def test_show_twice_is_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    face = await _face(db, fake_providers, user)

    first = (await _show(client, token, face.id)).json()
    second = (await _show(client, token, face.id)).json()

    assert second["id"] == first["id"]
    rows = await db.scalars(select(Photo.id).where(Photo.user_id == user.id))
    assert len(list(rows)) == 2


async def test_shown_the_copy_is_compared_for_the_badge_once_approved(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    fake_queue: FakeQueue,
) -> None:
    """The gap the founder named (8 October 2026): a woman whose only shown
    face is this copy must get the badge by the same path as any shown photo.
    Approved by moderation with a selfie kept, the copy is queued for
    comparison; until the job runs, no badge; then the badge."""
    from app.core.providers.facematch import FakeFaceMatch
    from app.modules.verification import repository as verification_repository
    from app.modules.verification import service as verification_service

    user, token = await _at(db, make_user, OnboardingStep.DONE)
    # A JPEG Pillow can decode: the copy is re-encoded and scored like any upload.
    face = await _face(db, fake_providers, user, data=jpeg("olive"))
    await _matched(db, user, fake_providers)
    copy_id = uuid.UUID((await _show(client, token, face.id)).json()["id"])
    assert not await verification_repository.shows_badge(db, user.id)

    assert (
        await service.moderate(
            Sessions(db),
            copy_id,
            storage=fake_providers.storage,
            moderation=fake_providers.moderation,
            queue=fake_queue,
            settings=make_test_settings(),
        )
        == "approved"
    )

    copy = await _fresh(db, copy_id)
    assert copy.moderation is not None
    assert (copy.status, copy.moderation["from_photo_id"]) == (
        ReviewStatus.APPROVED,
        str(face.id),
    )
    assert copy.public_key is not None
    [job] = fake_queue.named(MATCH_PHOTO)
    assert job.kwargs == {"photo_id": str(copy_id)}
    assert not await verification_repository.shows_badge(db, user.id)

    assert (
        await verification_service.match_photo(
            Sessions(db),
            copy_id,
            storage=fake_providers.storage,
            facematch=FakeFaceMatch(),
            settings=make_test_settings(),
        )
        == "matched"
    )

    assert await verification_repository.shows_badge(db, user.id)


async def test_hiding_it_again_is_removing_the_copy(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    face = await _face(db, fake_providers, user)
    copy_id = (await _show(client, token, face.id)).json()["id"]

    response = await client.delete(f"/v1/photos/{copy_id}", headers=_bearer(token))

    assert response.status_code == 204
    assert (await _fresh(db, uuid.UUID(copy_id))).reject_reason == "user_deleted"
    assert (await _fresh(db, face.id)).status is ReviewStatus.APPROVED
    # And the toggle can come on again: a new copy, since the old one went.
    again = (await _show(client, token, face.id)).json()
    assert again["id"] != copy_id


@pytest.mark.parametrize("status", [ReviewStatus.PENDING, ReviewStatus.REJECTED])
async def test_show_needs_an_approved_face_photo(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    status: ReviewStatus,
) -> None:
    user, token = await _at(db, make_user)
    face = await _face(db, fake_providers, user, status=status)

    response = await _show(client, token, face.id)

    assert response.status_code == 422
    assert _error(response) == {
        "code": "NOT_ALLOWED",
        "message": "Your face photo hasn't been approved yet.",
    }


async def test_show_with_no_free_place_says_to_make_room(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    for place in range(6):
        await _public(db, fake_providers, user, place)
    face = await _face(db, fake_providers, user)

    response = await _show(client, token, face.id)

    assert response.status_code == 422
    assert _error(response) == {
        "code": "NOT_ALLOWED",
        "message": "Remove a photo to make room first.",
        "details": {"max": 6},
    }


async def test_show_of_someone_elses_a_public_photo_or_none_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    other, _ = await _at(db, make_user)
    theirs = await _face(db, fake_providers, other)
    mine = await _public(db, fake_providers, user, 0)

    for photo_id in (theirs.id, mine.id, uuid.uuid4()):
        response = await _show(client, token, photo_id)
        assert (response.status_code, _error(response)["code"]) == (404, "NOT_FOUND")


async def test_show_before_the_photos_step_is_onboarding_incomplete(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user, OnboardingStep.ABOUT)
    face = await _face(db, fake_providers, user)

    response = await _show(client, token, face.id)

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"


@pytest.mark.usefixtures("db")
async def test_show_signed_out_is_refused(client: AsyncClient) -> None:
    response = await client.post(f"/v1/photos/{uuid.uuid4()}/show")

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"
