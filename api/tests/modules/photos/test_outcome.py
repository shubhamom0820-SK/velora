"""`GET /v1/photos/{id}`: how one of the owner's photos ended, rejected ones
included, so the slot that showed it can say why (T-4.6, D-096); and the
reasons an owner is told, by name only from a list (D-093)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers import FakeProviders
from app.modules.photos.models import Photo
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.images import JPEG

pytestmark = pytest.mark.usefixtures("test_redis")

PRIVATE = "velora-private"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _at_photos(db: AsyncSession, make_user: MakeUser) -> tuple[User, str]:
    user, token = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.PHOTOS
    await db.flush()
    return user, token


async def _photo(
    db: AsyncSession,
    fake_providers: FakeProviders,
    user: User,
    *,
    kind: PhotoKind = PhotoKind.PUBLIC,
    status: ReviewStatus = ReviewStatus.PENDING,
    reason: str | None = None,
) -> uuid.UUID:
    photo_id = uuid.uuid4()
    raw = f"raw/{user.id}/{photo_id}"
    db.add(
        Photo(
            id=photo_id,
            user_id=user.id,
            kind=kind,
            position=0 if kind is PhotoKind.PUBLIC else None,
            raw_key=raw,
            status=status,
            reject_reason=reason,
        )
    )
    await db.flush()
    await fake_providers.storage.put_bytes(PRIVATE, raw, JPEG, "image/jpeg")
    return photo_id


async def _get(client: AsyncClient, token: str, photo_id: Any) -> dict[str, Any]:
    response = await client.get(f"/v1/photos/{photo_id}", headers=_bearer(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_a_rejected_photo_left_the_list_but_still_says_why(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at_photos(db, make_user)
    photo_id = await _photo(
        db,
        fake_providers,
        user,
        status=ReviewStatus.REJECTED,
        reason="no_face",
    )

    listed = await client.get("/v1/me/photos", headers=_bearer(token))
    assert listed.json() == []

    assert await _get(client, token, photo_id) == {
        "id": str(photo_id),
        "kind": "public",
        "position": 0,
        "status": "rejected",
        "reject_reason": "no_face",
        "url": None,
        "from_photo_id": None,
    }


async def test_a_live_photo_reads_as_the_list_shows_it(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token = await _at_photos(db, make_user)
    photo_id = await _photo(db, fake_providers, user, kind=PhotoKind.PRIVATE)

    body = await _get(client, token, photo_id)

    assert (body["status"], body["kind"], body["reject_reason"]) == (
        "pending",
        "private",
        None,
    )
    assert body["url"] == (
        f"fake-storage://{PRIVATE}/raw/{user.id}/{photo_id}?method=GET&ttl=600"
    )


@pytest.mark.parametrize(
    "reason",
    [
        "abandoned",
        "too_large",
        "unsupported_format",
        "user_deleted",
        "replaced",
        "nudity",
        "no_face",
        "text_overlay",
        "other",
    ],
)
async def test_a_listed_reason_reaches_its_owner_by_name(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    reason: str,
) -> None:
    user, token = await _at_photos(db, make_user)
    photo_id = await _photo(
        db, fake_providers, user, status=ReviewStatus.REJECTED, reason=reason
    )

    assert (await _get(client, token, photo_id))["reject_reason"] == reason


@pytest.mark.parametrize("reason", ["minor_suspected", "a_reason_added_later"])
async def test_any_other_reason_reaches_its_owner_as_other(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    reason: str,
) -> None:
    """D-093: a possible minor is never named to the person, not even in the
    JSON a browser's tools show. A reason nobody listed fails closed the same
    way."""
    user, token = await _at_photos(db, make_user)
    photo_id = await _photo(
        db, fake_providers, user, status=ReviewStatus.REJECTED, reason=reason
    )

    response = await client.get(f"/v1/photos/{photo_id}", headers=_bearer(token))

    assert response.json()["reject_reason"] == "other"
    assert "minor" not in response.text
    assert reason not in response.text


async def test_someone_elses_photo_a_selfie_and_no_photo_answer_alike(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """The same 404 for each, so a photo id can't be probed."""
    owner, _ = await _at_photos(db, make_user)
    me, token = await _at_photos(db, make_user)
    theirs = await _photo(
        db, fake_providers, owner, status=ReviewStatus.REJECTED, reason="nudity"
    )
    selfie = await _photo(db, fake_providers, me, kind=PhotoKind.SELFIE)

    answers = [
        await client.get(f"/v1/photos/{photo_id}", headers=_bearer(token))
        for photo_id in (theirs, selfie, uuid.uuid4())
    ]

    assert [a.status_code for a in answers] == [404, 404, 404]
    assert len({a.text for a in answers}) == 1
    assert answers[0].json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.usefixtures("db")
async def test_it_needs_a_session(client: AsyncClient) -> None:
    response = await client.get(f"/v1/photos/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
