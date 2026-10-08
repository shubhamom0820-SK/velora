"""`POST /v1/me/photos/done` (T-4.12, D-391, D-392): the `photos` step's exit.
Anyone leaves with or without a public photo; anyone but a man needs a face
photo, pending or approved, by an allowlist; D-068's step rule."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core.enums import Gender, OnboardingStep, PhotoKind, ReviewStatus, Role
from app.core.security import make_access_token, normalize_phone
from app.modules.photos.models import Photo
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

STEPS = list(OnboardingStep)
BEFORE = STEPS[: STEPS.index(OnboardingStep.PHOTOS)]
AFTER = STEPS[STEPS.index(OnboardingStep.PHOTOS) + 1 :]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _done(client: AsyncClient, token: str) -> Response:
    return await client.post("/v1/me/photos/done", headers=_bearer(token))


async def _at(
    db: AsyncSession,
    make_user: MakeUser,
    gender: Gender | None = Gender.MALE,
    step: OnboardingStep = OnboardingStep.PHOTOS,
) -> tuple[User, str]:
    """Someone at `step` with no photo of any kind. No gender: the app can't
    produce them (gender is the second step, and immutable once set), so
    signup's own service makes the account and the step is set by hand; a
    woman at `done` is verified, as the database insists (D-310)."""
    if gender is None:
        settings = make_test_settings()
        phone = normalize_phone(f"+9195{uuid.uuid4().int % 10**8:08d}")
        account = await users_service.create_account(db, phone, settings)
        user = account.user
        token = make_access_token(
            user.id, Role.USER, settings, auth_time=core_clock.now()
        )
    else:
        user, token = await make_user(
            gender,
            onboarded=False,
            verified=gender is Gender.FEMALE and step is OnboardingStep.DONE,
        )
    user.onboarding_step = step
    await db.flush()
    return user, token


async def _photo(
    db: AsyncSession,
    user: User,
    kind: PhotoKind,
    status: ReviewStatus = ReviewStatus.APPROVED,
) -> uuid.UUID:
    photo_id = uuid.uuid4()
    db.add(
        Photo(
            id=photo_id,
            user_id=user.id,
            kind=kind,
            position=0 if kind is PhotoKind.PUBLIC else None,
            raw_key=f"raw/{user.id}/{photo_id}",
            status=status,
        )
    )
    await db.flush()
    return photo_id


async def _step(db: AsyncSession, user: User) -> OnboardingStep:
    await db.refresh(user)
    return user.onboarding_step


async def test_a_man_leaves_with_no_photo_at_all(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-392: nobody needs a public photo, men included; D-391: a man's selfie
    is optional, so the face photo it is compared with is too."""
    user, token = await _at(db, make_user)

    response = await _done(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "interests"
    assert await _step(db, user) is OnboardingStep.INTERESTS


@pytest.mark.parametrize("gender", [Gender.FEMALE, None], ids=["a woman", "no gender"])
async def test_anyone_but_a_man_needs_a_face_photo(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, gender: Gender | None
) -> None:
    """An allowlist (T-4.12's plan, point 2): a public photo, pending or
    approved, doesn't stand in for it; nothing moves until one is there."""
    user, token = await _at(db, make_user, gender)
    await _photo(db, user, PhotoKind.PUBLIC)
    await _photo(db, user, PhotoKind.PRIVATE)
    await _photo(db, user, PhotoKind.VERIFICATION, ReviewStatus.REJECTED)

    response = await _done(client, token)

    assert response.status_code == 403
    assert _error(response) == {
        "code": "FACE_PHOTO_REQUIRED",
        "message": "Add a photo of your face for the selfie check first.",
    }
    assert await _step(db, user) is OnboardingStep.PHOTOS


@pytest.mark.parametrize(
    "status", [ReviewStatus.PENDING, ReviewStatus.APPROVED], ids=["pending", "approved"]
)
async def test_a_face_photo_pending_or_approved_lets_a_woman_on(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, status: ReviewStatus
) -> None:
    """Pending is enough, as a pending public photo was (T-4.3): moderation
    takes seconds, and a `no_face` refusal sends her back from the selfie
    step's `no_photos`. No public photo is needed."""
    user, token = await _at(db, make_user, Gender.FEMALE)
    await _photo(db, user, PhotoKind.VERIFICATION, status)

    response = await _done(client, token)

    assert response.status_code == 200, response.text
    assert await _step(db, user) is OnboardingStep.INTERESTS


@pytest.mark.parametrize("step", BEFORE, ids=lambda s: s.value)
async def test_before_the_photos_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token = await _at(db, make_user, step=step)

    response = await _done(client, token)

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(response)["details"] == {"step": step.value}
    assert await _step(db, user) is step


@pytest.mark.parametrize("step", AFTER, ids=lambda s: s.value)
async def test_past_it_me_is_unchanged_and_nothing_is_checked(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    """D-068: an edit that doesn't advance; a woman with no face photo past
    the step (one removed before her match, say) isn't sent back."""
    user, token = await _at(db, make_user, Gender.FEMALE, step)

    response = await _done(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == step.value
    assert await _step(db, user) is step


@pytest.mark.usefixtures("db")
async def test_signed_out_is_refused(client: AsyncClient) -> None:
    response = await client.post("/v1/me/photos/done")

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"
