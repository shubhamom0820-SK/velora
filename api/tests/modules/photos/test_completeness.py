"""P-210: a finished profile's completeness kept current. Moderation's approval
of a public photo raises it, removing an approved one lowers it, a shown face
photo's copy included; before `done` nothing moves it (finishing sets it,
D-310), and neither a rejection nor removing a photo nobody saw changes it."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers import FakeProviders
from app.core.providers.moderation import FakeModeration
from app.core.providers.storage import FakeStorage
from app.modules.onboarding import rules as onboarding_rules
from app.modules.photos.models import Photo
from app.modules.photos.service import FROM_PHOTO_ID
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.images import JPEG
from tests.modules.photos.test_moderate import _moderate, _pending

pytestmark = pytest.mark.usefixtures("test_redis")

PUBLIC, PRIVATE = "velora-public", "velora-private"


async def _completeness(db: AsyncSession, user_id: uuid.UUID) -> int:
    found = await db.scalar(
        select(Profile.completeness)
        .where(Profile.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _finished(
    db: AsyncSession, make_user: MakeUser, approved: int
) -> tuple[User, str, uuid.UUID]:
    """Someone who finished with `approved` public photos shown, at the
    completeness finishing gave them (D-310)."""
    user, token = await make_user()
    for place in range(approved):
        await _shown(db, user, place)
    profile = await db.get(Profile, user.id)
    assert profile is not None
    profile.completeness = onboarding_rules.completeness(approved)
    await db.flush()
    return user, token, user.id


async def _shown(
    db: AsyncSession,
    user: User,
    place: int,
    *,
    status: ReviewStatus = ReviewStatus.APPROVED,
    made_from: uuid.UUID | None = None,
    storage: FakeStorage | None = None,
) -> uuid.UUID:
    photo_id = uuid.uuid4()
    approved = status is ReviewStatus.APPROVED
    db.add(
        Photo(
            id=photo_id,
            user_id=user.id,
            kind=PhotoKind.PUBLIC,
            position=place,
            raw_key=f"raw/{user.id}/{photo_id}",
            public_key=f"p/{photo_id}.jpg" if approved else None,
            status=status,
            moderation={FROM_PHOTO_ID: str(made_from)} if made_from else None,
        )
    )
    await db.flush()
    if storage is not None:
        await storage.put_bytes(
            PRIVATE, f"raw/{user.id}/{photo_id}", JPEG, "image/jpeg"
        )
    return photo_id


async def test_an_approval_after_finishing_raises_it(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _, user_id = await _finished(db, make_user, approved=2)
    assert await _completeness(db, user_id) == 60
    photo = await _pending(db, storage, user, position=2)

    assert await _moderate(db, photo, storage, moderation) == "approved"

    assert await _completeness(db, user_id) == 70


async def test_an_approval_at_none_or_one_stays_at_50(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-392's rule unchanged: the first photo adds nothing."""
    storage, moderation = FakeStorage(), FakeModeration()
    user, _, user_id = await _finished(db, make_user, approved=0)
    photo = await _pending(db, storage, user, position=0)

    assert await _moderate(db, photo, storage, moderation) == "approved"

    assert await _completeness(db, user_id) == 50


async def test_a_rejection_changes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _, user_id = await _finished(db, make_user, approved=3)
    photo = await _pending(db, storage, user, position=3)
    moderation.next = "reject:nudity"

    assert await _moderate(db, photo, storage, moderation) == "nudity"

    assert await _completeness(db, user_id) == 70


async def test_before_finishing_an_approval_leaves_it_to_finishing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.PHOTOS
    await db.flush()
    for place in range(2):
        await _shown(db, user, place)
    photo = await _pending(db, storage, user, position=2)

    assert await _moderate(db, photo, storage, moderation) == "approved"

    assert await _completeness(db, user.id) == 0


@pytest.mark.parametrize("face_photos_copy", [False, True])
async def test_removing_an_approved_public_photo_lowers_it(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    face_photos_copy: bool,
) -> None:
    """A shown face photo turned off is `user_deleted` on its public copy
    (T-4.12, D-400), so it lowers it the same way."""
    user, token, user_id = await _finished(db, make_user, approved=3)
    copy = await _shown(
        db,
        user,
        3,
        made_from=uuid.uuid4() if face_photos_copy else None,
        storage=fake_providers.storage,
    )
    profile = await db.get(Profile, user_id)
    assert profile is not None
    profile.completeness = onboarding_rules.completeness(4)
    await db.flush()

    response = await client.delete(
        f"/v1/photos/{copy}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert await _completeness(db, user_id) == 70


async def test_removing_a_photo_nobody_saw_changes_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, token, user_id = await _finished(db, make_user, approved=2)
    waiting = await _shown(
        db, user, 2, status=ReviewStatus.PENDING, storage=fake_providers.storage
    )

    response = await client.delete(
        f"/v1/photos/{waiting}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert await _completeness(db, user_id) == 60
