"""`GET /v1/me/photos`, `PATCH /v1/me/photos/order`, `DELETE /v1/photos/{id}`
(T-4.3); and, from T-4.12, no photo completing the `photos` step, the last
public photo removable past it (D-392), the face photo listed to its owner and
removable until the selfie matched (D-391)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers import FakeProviders
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification.models import Verification
from tests.conftest import MakeUser
from tests.images import HEIC, JPEG

pytestmark = pytest.mark.usefixtures("test_redis")

PUBLIC, PRIVATE = "velora-public", "velora-private"


@dataclass(frozen=True)
class Stored:
    id: uuid.UUID
    raw_key: str
    public_key: str | None
    scored_key: str | None = None


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


async def _photo(
    db: AsyncSession,
    fake_providers: FakeProviders,
    user: User,
    *,
    kind: PhotoKind = PhotoKind.PUBLIC,
    position: int | None = 0,
    status: ReviewStatus = ReviewStatus.APPROVED,
) -> Stored:
    """A photo as moderation would leave it: its private copy stored, an
    approved public one's public copy too, and an approved private one's
    scored copy (P-79, D-700). Returned as a snapshot, since a request's
    commit expires the ORM object a test holds."""
    photo_id = uuid.uuid4()
    raw = f"raw/{user.id}/{photo_id}"
    public_key = (
        f"p/{photo_id}.jpg"
        if kind is PhotoKind.PUBLIC and status is ReviewStatus.APPROVED
        else None
    )
    scored_key = (
        f"scored/{user.id}/{photo_id}.jpg"
        if kind is PhotoKind.PRIVATE and status is ReviewStatus.APPROVED
        else None
    )
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=kind,
        position=position,
        raw_key=raw,
        public_key=public_key,
        scored_key=scored_key,
        status=status,
    )
    db.add(photo)
    await db.flush()
    await fake_providers.storage.put_bytes(PRIVATE, raw, JPEG, "image/jpeg")
    if public_key:
        await fake_providers.storage.put_bytes(PUBLIC, public_key, JPEG, "image/jpeg")
    if scored_key:
        await fake_providers.storage.put_bytes(PRIVATE, scored_key, JPEG, "image/jpeg")
    return Stored(photo_id, raw, public_key, scored_key)


async def _fresh(db: AsyncSession, photo_id: uuid.UUID) -> Photo:
    """Read back by id: a request's commit expires the objects a test holds."""
    found = await db.scalar(select(Photo).where(Photo.id == photo_id))
    assert found is not None
    await db.refresh(found)
    return found


async def _list(client: AsyncClient, token: str) -> list[dict[str, Any]]:
    response = await client.get("/v1/me/photos", headers=_bearer(token))
    assert response.status_code == 200, response.text
    photos: list[dict[str, Any]] = response.json()
    return photos


async def _order(client: AsyncClient, token: str, ids: list[Any]) -> Response:
    return await client.patch(
        "/v1/me/photos/order",
        json={"photo_ids": [str(i) for i in ids]},
        headers=_bearer(token),
    )


async def _delete(client: AsyncClient, token: str, photo_id: Any) -> Response:
    return await client.delete(f"/v1/photos/{photo_id}", headers=_bearer(token))


# --- The owner's photos --------------------------------------------------------------


async def test_the_owner_sees_every_live_photo_and_where_to_view_it(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    main = await _photo(db, fake_providers, user, position=0)
    pending = await _photo(
        db, fake_providers, user, position=1, status=ReviewStatus.PENDING
    )
    private = await _photo(
        db, fake_providers, user, kind=PhotoKind.PRIVATE, position=None
    )

    photos = await _list(client, token)

    assert [p["id"] for p in photos] == [str(main.id), str(pending.id), str(private.id)]
    # Approved and public: the CDN. Approved and private: a signed link to its
    # scored copy, never the upload a second PUT could have replaced (P-79).
    # Anything else: a signed link to the upload, 10 minutes.
    assert photos[0]["url"] == f"/{main.public_key}"
    assert (
        photos[1]["url"]
        == f"fake-storage://{PRIVATE}/{pending.raw_key}?method=GET&ttl=600"
    )
    assert private.scored_key == f"scored/{user.id}/{private.id}.jpg"
    assert (
        photos[2]["url"]
        == f"fake-storage://{PRIVATE}/{private.scored_key}?method=GET&ttl=600"
    )


async def test_not_listed_rejected_photos_selfies_or_anyone_elses(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user, OnboardingStep.SELFIE)
    other, _ = await _at(db, make_user)
    await _photo(db, fake_providers, user, position=0, status=ReviewStatus.REJECTED)
    await _photo(db, fake_providers, user, kind=PhotoKind.SELFIE, position=None)
    await _photo(db, fake_providers, other, position=0)
    await _photo(db, fake_providers, other, kind=PhotoKind.VERIFICATION, position=None)

    assert await _list(client, token) == []


async def test_the_face_photo_is_listed_last_to_its_owner_by_a_signed_link(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """D-391: private, so never at the CDN; after the public and private
    photos, so the grid's places are untouched (T-4.12)."""
    user, token = await _at(db, make_user)
    main = await _photo(db, fake_providers, user, position=0)
    private = await _photo(
        db, fake_providers, user, kind=PhotoKind.PRIVATE, position=None
    )
    face = await _photo(
        db, fake_providers, user, kind=PhotoKind.VERIFICATION, position=None
    )

    photos = await _list(client, token)

    assert [(p["id"], p["kind"]) for p in photos] == [
        (str(main.id), "public"),
        (str(private.id), "private"),
        (str(face.id), "verification"),
    ]
    assert photos[2]["url"] == (
        f"fake-storage://{PRIVATE}/{face.raw_key}?method=GET&ttl=600"
    )
    assert face.public_key is None


async def test_signed_out_sees_nothing(db: AsyncSession, client: AsyncClient) -> None:
    response = await client.get("/v1/me/photos")

    assert _error(response)["code"] == "AUTH_REQUIRED"


# --- Order ---------------------------------------------------------------------------------


async def test_two_photos_swap_places_and_keep_their_statuses(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """A swap: each wants the other's place, which the one-per-place index
    checked row by row would refuse halfway through (set_positions)."""
    user, token = await _at(db, make_user)
    first = await _photo(db, fake_providers, user, position=0)
    second = await _photo(
        db, fake_providers, user, position=1, status=ReviewStatus.PENDING
    )

    response = await _order(client, token, [second.id, first.id])

    assert response.status_code == 200, response.text
    assert [(p["id"], p["position"], p["status"]) for p in response.json()] == [
        (str(second.id), 0, "pending"),
        (str(first.id), 1, "approved"),
    ]
    assert (
        (await _fresh(db, first.id)).position,
        (await _fresh(db, second.id)).position,
    ) == (1, 0)


async def test_order_closes_the_gaps_first_is_main(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    a = await _photo(db, fake_providers, user, position=5)
    b = await _photo(db, fake_providers, user, position=2)
    c = await _photo(db, fake_providers, user, position=0)

    response = await _order(client, token, [a.id, b.id, c.id])

    assert [(p["id"], p["position"]) for p in response.json()] == [
        (str(a.id), 0),
        (str(b.id), 1),
        (str(c.id), 2),
    ]


@pytest.mark.parametrize("wrong", ["partial", "someone else's", "unknown", "twice"])
async def test_order_must_be_exactly_the_live_public_photos(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    wrong: str,
) -> None:
    user, token = await _at(db, make_user)
    other, _ = await _at(db, make_user)
    first = await _photo(db, fake_providers, user, position=0)
    second = await _photo(db, fake_providers, user, position=1)
    theirs = await _photo(db, fake_providers, other, position=0)
    ids = {
        "partial": [first.id],
        "someone else's": [first.id, theirs.id],
        "unknown": [first.id, second.id, uuid.uuid4()],
        "twice": [first.id, second.id, first.id],
    }[wrong]

    response = await _order(client, token, ids)

    assert response.status_code == 400
    assert _error(response)["details"]["fields"][0]["field"] == "photo_ids"
    assert (
        (await _fresh(db, first.id)).position,
        (await _fresh(db, second.id)).position,
    ) == (0, 1)


async def test_order_before_the_photos_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _order(client, token, [uuid.uuid4()])

    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"


# --- Delete ----------------------------------------------------------------------------------


async def test_a_deleted_photo_leaves_its_place_and_the_public_bucket(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Soft: rejected as `user_deleted`, the public copy removed, the private
    copy and the row kept."""
    user, token = await _at(db, make_user)
    photo = await _photo(db, fake_providers, user, position=0)
    await _photo(db, fake_providers, user, position=1)

    response = await _delete(client, token, photo.id)

    assert response.status_code == 204
    gone = await _fresh(db, photo.id)
    assert (gone.status, gone.reject_reason) == (ReviewStatus.REJECTED, "user_deleted")
    assert (PUBLIC, photo.public_key) not in fake_providers.storage.objects
    assert (PRIVATE, photo.raw_key) in fake_providers.storage.objects
    again = await client.post(
        "/v1/photos/upload-url",
        json={"kind": "public", "position": 0, "content_type": "image/jpeg"},
        headers=_bearer(token),
    )
    assert again.status_code == 200


async def test_deleting_twice_is_deleting_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    photo = await _photo(
        db, fake_providers, user, kind=PhotoKind.PRIVATE, position=None
    )

    first = await _delete(client, token, photo.id)
    second = await _delete(client, token, photo.id)

    assert (first.status_code, second.status_code) == (204, 204)


async def test_someone_elses_photo_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    owner, _ = await _at(db, make_user)
    _, other = await _at(db, make_user)
    photo = await _photo(db, fake_providers, owner, position=0)

    theirs = await _delete(client, other, photo.id)
    nobodys = await _delete(client, other, uuid.uuid4())

    assert theirs.status_code == nobodys.status_code == 404
    assert theirs.json() == nobodys.json()
    assert (await _fresh(db, photo.id)).status is ReviewStatus.APPROVED


async def test_a_selfie_isnt_removed_here(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user, OnboardingStep.SELFIE)
    selfie = await _photo(
        db, fake_providers, user, kind=PhotoKind.SELFIE, position=None
    )

    response = await _delete(client, token, selfie.id)

    assert _error(response)["code"] == "NOT_ALLOWED"


@pytest.mark.parametrize(
    "step", [OnboardingStep.INTERESTS, OnboardingStep.DONE], ids=["later", "done"]
)
async def test_the_last_public_photo_can_go_past_the_photos_step_too(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    step: OnboardingStep,
) -> None:
    """D-392 (T-4.12): nobody needs a public photo, so the last one goes as
    any other; until then T-4.3 kept it, since discovery needed one."""
    user, token = await _at(db, make_user, step)
    last = await _photo(db, fake_providers, user, position=0)

    response = await _delete(client, token, last.id)

    assert response.status_code == 204
    assert (await _fresh(db, last.id)).reject_reason == "user_deleted"
    assert await _list(client, token) == []


async def _matched(db: AsyncSession, user: User, selfie_id: uuid.UUID) -> None:
    """The selfie matched: `is_verified`, T-4.5's own word, and its approved
    verification."""
    user.is_verified = True
    db.add(
        Verification(
            user_id=user.id,
            challenge="none",
            selfie_photo_id=selfie_id,
            status=ReviewStatus.APPROVED,
        )
    )
    await db.flush()


async def test_the_face_photo_goes_until_the_selfie_matched(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Removed as any photo before the match, `user_deleted`, no public copy
    to remove; after it, refused, so the match never points at a photo that
    is gone (T-4.12's plan, point 4; a change then is P-163's path)."""
    user, token = await _at(db, make_user, OnboardingStep.DONE)
    before = await _photo(
        db, fake_providers, user, kind=PhotoKind.VERIFICATION, position=None
    )
    assert (await _delete(client, token, before.id)).status_code == 204
    assert (await _fresh(db, before.id)).reject_reason == "user_deleted"

    after = await _photo(
        db, fake_providers, user, kind=PhotoKind.VERIFICATION, position=None
    )
    selfie = await _photo(
        db, fake_providers, user, kind=PhotoKind.SELFIE, position=None
    )
    await _matched(db, user, selfie.id)

    response = await _delete(client, token, after.id)

    assert response.status_code == 422
    assert _error(response) == {
        "code": "NOT_ALLOWED",
        "message": "Your face photo can't change once your selfie matched.",
    }
    assert (await _fresh(db, after.id)).status is ReviewStatus.APPROVED


async def test_the_face_photo_stays_while_the_selfie_is_compared(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The worker may be reading it this moment: a verification holding a
    selfie and not yet decided keeps it where it is."""
    user, token = await _at(db, make_user, OnboardingStep.SELFIE)
    face = await _photo(
        db, fake_providers, user, kind=PhotoKind.VERIFICATION, position=None
    )
    selfie = await _photo(
        db, fake_providers, user, kind=PhotoKind.SELFIE, position=None
    )
    db.add(Verification(user_id=user.id, challenge="none", selfie_photo_id=selfie.id))
    await db.flush()

    response = await _delete(client, token, face.id)

    assert response.status_code == 422
    assert _error(response)["message"] == (
        "Your face photo can't change while your selfie is compared."
    )


async def test_at_the_photos_step_the_last_one_can_go(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at(db, make_user)
    only = await _photo(db, fake_providers, user, position=0)

    assert (await _delete(client, token, only.id)).status_code == 204


# --- The photos step ------------------------------------------------------------------------


async def _upload_and_complete(
    client: AsyncClient,
    db: AsyncSession,
    fake_providers: FakeProviders,
    token: str,
    data: bytes,
    *,
    kind: str = "public",
    position: int | None = 0,
) -> Response:
    body: dict[str, Any] = {"kind": kind, "content_type": "image/jpeg"}
    if position is not None:
        body["position"] = position
    url = await client.post("/v1/photos/upload-url", json=body, headers=_bearer(token))
    photo_id = url.json()["photo_id"]
    photo = await db.scalar(select(Photo).where(Photo.id == uuid.UUID(photo_id)))
    assert photo is not None
    await fake_providers.storage.put_bytes(PRIVATE, photo.raw_key, data, "image/jpeg")
    return await client.post(f"/v1/photos/{photo_id}/complete", headers=_bearer(token))


@pytest.mark.parametrize(
    ("step", "kind", "position", "data", "after"),
    [
        (OnboardingStep.PHOTOS, "public", 0, JPEG, OnboardingStep.PHOTOS),
        (OnboardingStep.PHOTOS, "private", None, JPEG, OnboardingStep.PHOTOS),
        (OnboardingStep.PHOTOS, "verification", None, JPEG, OnboardingStep.PHOTOS),
        (OnboardingStep.PHOTOS, "public", 0, HEIC, OnboardingStep.PHOTOS),
        (OnboardingStep.INTERESTS, "public", 0, JPEG, OnboardingStep.INTERESTS),
    ],
    ids=[
        "public-doesnt-complete-the-step",
        "private-doesnt",
        "the-face-photo-doesnt",
        "a-refused-one-doesnt",
        "after-it-an-edit",
    ],
)
async def test_no_photo_completes_the_photos_step(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    step: OnboardingStep,
    kind: str,
    position: int | None,
    data: bytes,
    after: OnboardingStep,
) -> None:
    """D-392 (T-4.12): no photo moves the step on; `POST /me/photos/done` is
    its exit (`tests/modules/onboarding/test_leave_photos.py`). Until T-4.12 a
    public photo, pending or approved, did (T-4.3)."""
    user, token = await _at(db, make_user, step)

    await _upload_and_complete(
        client, db, fake_providers, token, data, kind=kind, position=position
    )

    await db.refresh(user)
    assert user.onboarding_step is after
