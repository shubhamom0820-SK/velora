"""`POST /v1/me/onboarding/complete` (T-4.8, D-310): the `selfie` step's way to
`done`. Every requirement met, and a selfie that matched for anyone but a man;
each requirement refused on its own, by name; D-068's step rule; and the
completeness it leaves."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, get_args

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core.config import Settings
from app.core.enums import (
    Gender,
    OnboardingStep,
    PhotoKind,
    ReviewStatus,
    Role,
    Seeking,
)
from app.core.security import make_access_token, normalize_phone
from app.modules.onboarding.rules import Missing
from app.modules.photos.models import Photo
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.verification.models import Verification
from tests.conftest import MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

STEPS = list(OnboardingStep)
BEFORE = STEPS[: STEPS.index(OnboardingStep.SELFIE)]

# Beside Model Town's centroid in Phagwara, as T-4.10's tests put people.
NEAR_MODEL_TOWN = (31.2139, 75.7680)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _complete(client: AsyncClient, token: str) -> Response:
    return await client.post("/v1/me/onboarding/complete", headers=_bearer(token))


async def _photo(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    kind: PhotoKind = PhotoKind.PUBLIC,
    status: ReviewStatus = ReviewStatus.APPROVED,
    position: int | None = 0,
    removed: bool = False,
) -> uuid.UUID:
    """A photo as moderation leaves it: an approved public one has its public
    copy; nothing else does. `removed`: approved, then removed by its owner,
    which rejects it as `user_deleted` and keeps its `public_key` (T-4.3)."""
    photo_id = uuid.uuid4()
    public = kind is PhotoKind.PUBLIC and (status is ReviewStatus.APPROVED or removed)
    if removed:
        status = ReviewStatus.REJECTED
    db.add(
        Photo(
            id=photo_id,
            user_id=user_id,
            kind=kind,
            position=position if kind is PhotoKind.PUBLIC else None,
            raw_key=f"raw/{user_id}/{photo_id}",
            public_key=f"p/{photo_id}.jpg" if public else None,
            status=status,
            reject_reason="user_deleted" if removed else None,
        )
    )
    await db.flush()
    return photo_id


async def _ready(
    db: AsyncSession, user: User, *, step: OnboardingStep = OnboardingStep.SELFIE
) -> uuid.UUID:
    """Everything a finished profile needs, as the screens leave it: Name and
    places, a location, a username, an about, one approved public photo at
    place 0, five interests, one intent. Returns the photo's id."""
    user.onboarding_step = step
    profile = await db.get(Profile, user.id)
    assert profile is not None
    profile.seeking = Seeking.WOMEN if user.gender is Gender.MALE else Seeking.MEN
    profile.first_name = "Test"
    profile.hometown = "Jalandhar"
    profile.city = "Phagwara"
    profile.location = profiles_repository.point(*NEAR_MODEL_TOWN)
    profile.username = f"ready{uuid.uuid4().hex[:12]}"
    profile.about = "A profile ready to finish, with an about long enough to pass."
    db.add(ProfileIntent(user_id=user.id, intent_id=1))
    db.add_all(
        ProfileInterest(user_id=user.id, interest_id=interest_id)
        for interest_id in range(1, 6)
    )
    await db.flush()
    return await _photo(db, user.id)


async def _at_selfie(
    db: AsyncSession,
    make_user: MakeUser,
    gender: Gender = Gender.MALE,
    *,
    verified: bool = False,
) -> tuple[User, str, uuid.UUID]:
    """Someone at the `selfie` step with everything else in place: the user,
    their token and their id, read now (a refused request rolls back and
    expires the loaded user)."""
    user, token = await make_user(gender, onboarded=False, verified=verified)
    await _ready(db, user)
    return user, token, user.id


async def _stored(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, int]:
    """The step and the completeness as the database holds them now."""
    row = (
        await db.execute(
            text(
                "select u.onboarding_step::text, p.completeness from users u "
                "join profiles p on p.user_id = u.id where u.id = :id"
            ),
            {"id": user_id},
        )
    ).one()
    return str(row[0]), int(row[1])


# --- Finishing ----------------------------------------------------------------------


async def test_a_man_finishes_without_a_selfie(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at_selfie(db, make_user, Gender.MALE)

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["onboarding_step"], body["is_verified"]) == ("done", False)
    assert await _stored(db, user_id) == ("done", 50)


async def test_a_woman_whose_selfie_matched_finishes(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at_selfie(db, make_user, Gender.FEMALE, verified=True)

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "done"
    assert await _stored(db, user_id) == ("done", 50)


async def test_completeness_counts_approved_public_photos_only(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Three approved public photos make 70 (D-310). A pending public one, one
    rejected, one its owner removed (its `public_key` kept), an approved
    private one and a selfie add nothing."""
    _, token, user_id = await _at_selfie(db, make_user)
    await _photo(db, user_id, position=1)
    await _photo(db, user_id, position=2)
    await _photo(db, user_id, position=3, status=ReviewStatus.PENDING)
    await _photo(db, user_id, position=4, status=ReviewStatus.REJECTED)
    await _photo(db, user_id, position=5, removed=True)
    await _photo(db, user_id, kind=PhotoKind.PRIVATE)
    await _photo(db, user_id, kind=PhotoKind.SELFIE)

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert await _stored(db, user_id) == ("done", 70)


# --- Each requirement, refused by name -------------------------------------------------

Break = Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[None]]


def _clear(column: str) -> Break:
    async def clear(db: AsyncSession, user_id: uuid.UUID, _: uuid.UUID) -> None:
        values: dict[str, Any] = {column: None}
        if column == "location":
            values["location_updated_at"] = None
        await db.execute(
            update(Profile).where(Profile.user_id == user_id).values(**values)
        )

    return clear


async def _no_intents(db: AsyncSession, user_id: uuid.UUID, _: uuid.UUID) -> None:
    await db.execute(delete(ProfileIntent).where(ProfileIntent.user_id == user_id))


async def _four_intents(db: AsyncSession, user_id: uuid.UUID, _: uuid.UUID) -> None:
    db.add_all(ProfileIntent(user_id=user_id, intent_id=i) for i in range(2, 5))
    await db.flush()


async def _four_interests(db: AsyncSession, user_id: uuid.UUID, _: uuid.UUID) -> None:
    await db.execute(
        delete(ProfileInterest).where(
            ProfileInterest.user_id == user_id, ProfileInterest.interest_id == 5
        )
    )


def _photo_as(**values: Any) -> Break:
    async def change(db: AsyncSession, _: uuid.UUID, photo_id: uuid.UUID) -> None:
        await db.execute(update(Photo).where(Photo.id == photo_id).values(**values))

    return change


async def _no_photo(db: AsyncSession, _: uuid.UUID, photo_id: uuid.UUID) -> None:
    await db.execute(delete(Photo).where(Photo.id == photo_id))


BREAKS: dict[str, tuple[Missing, Break]] = {
    "no seeking": ("seeking", _clear("seeking")),
    "no intent": ("intents", _no_intents),
    "four intents": ("intents", _four_intents),
    "no first name": ("first_name", _clear("first_name")),
    "no hometown": ("hometown", _clear("hometown")),
    "no city": ("city", _clear("city")),
    "no location": ("location", _clear("location")),
    "no username": ("username", _clear("username")),
    "no about": ("about", _clear("about")),
    "no photo": ("photo", _no_photo),
    "a photo still being checked": (
        "photo",
        _photo_as(status=ReviewStatus.PENDING, public_key=None),
    ),
    "a photo rejected by moderation": (
        "photo",
        _photo_as(
            status=ReviewStatus.REJECTED, reject_reason="nudity", public_key=None
        ),
    ),
    # As `DELETE /photos/{id}` leaves an approved one: rejected, its
    # `public_key` kept though the public copy is gone (T-4.3).
    "a photo its owner removed": (
        "photo",
        _photo_as(status=ReviewStatus.REJECTED, reject_reason="user_deleted"),
    ),
    "a private photo only": (
        "photo",
        _photo_as(kind=PhotoKind.PRIVATE, position=None, public_key=None),
    ),
    "a selfie only": (
        "photo",
        _photo_as(kind=PhotoKind.SELFIE, position=None, public_key=None),
    ),
    "four interests": ("interests", _four_interests),
}


def test_every_requirement_has_a_case() -> None:
    assert {missing for missing, _ in BREAKS.values()} == set(get_args(Missing))


@pytest.mark.parametrize("case", list(BREAKS))
async def test_each_requirement_is_refused_by_name(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, case: str
) -> None:
    """A man, so the selfie can't be why: each one alone is `PROFILE_INCOMPLETE`,
    naming exactly it, and nothing moves."""
    requirement, break_it = BREAKS[case]
    _, token, user_id = await _at_selfie(db, make_user)
    photo_id = await db.scalar(
        text("select id from photos where user_id = :u"), {"u": user_id}
    )
    await break_it(db, user_id, photo_id)
    db.expire_all()

    response = await _complete(client, token)

    assert response.status_code == 403, response.text
    error = _error(response)
    assert (error["code"], error["details"]) == (
        "PROFILE_INCOMPLETE",
        {"missing": [requirement]},
    )
    assert await _stored(db, user_id) == ("selfie", 0)


async def test_everything_missing_is_named_in_onboardings_order(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The first named is the earliest screen to go back to."""
    _, token, user_id = await _at_selfie(db, make_user)
    photo_id = await db.scalar(
        text("select id from photos where user_id = :u"), {"u": user_id}
    )
    for _, break_it in BREAKS.values():
        if break_it is not _four_intents:
            await break_it(db, user_id, photo_id)
    db.expire_all()

    response = await _complete(client, token)

    assert response.status_code == 403
    assert _error(response)["details"] == {"missing": list(get_args(Missing))}
    assert await _stored(db, user_id) == ("selfie", 0)


# --- The selfie: men only may finish without a match ------------------------------------


async def _verification(
    db: AsyncSession, user_id: uuid.UUID, status: ReviewStatus, *, submitted: bool
) -> None:
    selfie_id = None
    if submitted:
        selfie_id = await _photo(
            db, user_id, kind=PhotoKind.SELFIE, status=ReviewStatus.PENDING
        )
        if status is ReviewStatus.REJECTED:
            await db.execute(
                update(Photo)
                .where(Photo.id == selfie_id)
                .values(status=ReviewStatus.REJECTED, reject_reason="no_match")
            )
    db.add(
        Verification(
            user_id=user_id, challenge="none", selfie_photo_id=selfie_id, status=status
        )
    )
    await db.flush()


SELFIES: dict[str, tuple[ReviewStatus, bool] | None] = {
    "none sent": None,
    "started, no selfie yet": (ReviewStatus.PENDING, False),
    "being compared": (ReviewStatus.PENDING, True),
    "didn't match": (ReviewStatus.REJECTED, True),
}


@pytest.mark.critical  # 06-TESTING.md #8b
@pytest.mark.parametrize("selfie", list(SELFIES))
async def test_a_woman_without_a_match_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, selfie: str
) -> None:
    _, token, user_id = await _at_selfie(db, make_user, Gender.FEMALE)
    if (verification := SELFIES[selfie]) is not None:
        await _verification(db, user_id, verification[0], submitted=verification[1])

    response = await _complete(client, token)

    assert response.status_code == 403, response.text
    assert _error(response)["code"] == "VERIFICATION_REQUIRED"
    assert _error(response).get("details") is None
    assert await _stored(db, user_id) == ("selfie", 0)


async def _no_gender(db: AsyncSession, settings: Settings) -> tuple[uuid.UUID, str]:
    """Someone at the `selfie` step with no gender: the app can't produce
    them (gender is the second step), so only the allowlist decides."""
    phone = normalize_phone(f"+9195{uuid.uuid4().int % 10**8:08d}")
    account = await users_service.create_account(db, phone, settings)
    await _ready(db, account.user)
    token = make_access_token(
        account.user.id, Role.USER, settings, auth_time=core_clock.now()
    )
    return account.user.id, token


@pytest.mark.critical  # 06-TESTING.md #8b: the case that makes it an allowlist
async def test_no_gender_needs_a_match_too(
    db: AsyncSession, client: AsyncClient
) -> None:
    user_id, token = await _no_gender(db, make_test_settings())

    response = await _complete(client, token)

    assert response.status_code == 403, response.text
    assert _error(response)["code"] == "VERIFICATION_REQUIRED"
    assert await _stored(db, user_id) == ("selfie", 0)


async def test_a_profile_short_of_something_is_told_that_before_the_selfie(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The selfie is compared with the photos, so a missing photo comes first."""
    _, token, user_id = await _at_selfie(db, make_user, Gender.FEMALE)
    await db.execute(delete(Photo).where(Photo.user_id == user_id))

    response = await _complete(client, token)

    assert response.status_code == 403
    assert (_error(response)["code"], _error(response)["details"]) == (
        "PROFILE_INCOMPLETE",
        {"missing": ["photo"]},
    )


# --- D-068's step rule ------------------------------------------------------------------


@pytest.mark.parametrize("step", BEFORE, ids=lambda s: s.value)
async def test_before_the_selfie_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    """Even with everything in place: the steps are walked in order."""
    user, token = await make_user(Gender.MALE, onboarded=False)
    await _ready(db, user, step=step)
    user_id = user.id

    response = await _complete(client, token)

    assert response.status_code == 403
    error = _error(response)
    assert (error["code"], error["details"]) == (
        "ONBOARDING_INCOMPLETE",
        {"step": step.value},
    )
    assert await _stored(db, user_id) == (step.value, 0)


async def test_once_done_it_changes_nothing_and_checks_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """`make_user`'s finished man has no photo or interests: done is done, and
    asking again neither refuses him nor recomputes (P-210 keeps it current)."""
    user, token = await make_user(Gender.MALE)
    user_id = user.id

    response = await _complete(client, token)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "done"
    assert await _stored(db, user_id) == ("done", 0)


async def test_twice_is_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at_selfie(db, make_user)
    first = await _complete(client, token)
    await _photo(db, user_id, position=1)

    second = await _complete(client, token)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()
    assert await _stored(db, user_id) == ("done", 50)


@pytest.mark.usefixtures("db")
async def test_signed_out_is_refused(client: AsyncClient) -> None:
    response = await client.post("/v1/me/onboarding/complete")

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"
