"""What T-4.5's tests share: a person at the selfie step, their face photo
(T-4.12), their public photos and selfie with files in the fake storage, and
the three requests."""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import Any

from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers.storage import FakeStorage
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification.models import Verification
from tests.conftest import MakeUser

PUBLIC, PRIVATE = "velora-public", "velora-private"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def error(response: Response) -> dict[str, Any]:
    found: dict[str, Any] = response.json()["error"]
    return found


def jpeg(colour: str = "teal", size: tuple[int, int] = (640, 800)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "JPEG")
    return out.getvalue()


async def at_selfie(
    db: AsyncSession, make_user: MakeUser, gender: Gender | str = Gender.FEMALE
) -> tuple[User, str]:
    """Someone at D-068's `selfie` step: unverified, with no selfie yet."""
    user, token = await make_user(gender, onboarded=False)
    user.onboarding_step = OnboardingStep.SELFIE
    await db.flush()
    return user, token


async def approved_photo(
    db: AsyncSession,
    storage: FakeStorage,
    user: User,
    *,
    position: int = 0,
    data: bytes | None = None,
    faces: int = 1,
) -> Photo:
    """An approved public photo, as moderation leaves one: a private copy, the
    public one it scored, and a record saying how many real faces it found
    (`faces`, which the badge's comparison reads, D-393)."""
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=PhotoKind.PUBLIC,
        position=position,
        raw_key=f"raw/{user.id}/{photo_id}",
        public_key=f"p/{photo_id}.jpg",
        status=ReviewStatus.APPROVED,
        moderation={"provider": "sightengine", "faces": faces},
    )
    db.add(photo)
    await db.flush()
    body = data or jpeg("navy")
    await storage.put_bytes(PRIVATE, photo.raw_key, body, "image/jpeg")
    await storage.put_bytes(PUBLIC, f"p/{photo_id}.jpg", body, "image/jpeg")
    return photo


async def face_photo(
    db: AsyncSession,
    storage: FakeStorage,
    user: User,
    *,
    status: ReviewStatus = ReviewStatus.APPROVED,
    data: bytes | None = None,
) -> Photo:
    """The face photo (T-4.12, D-391) as moderation leaves one: approved, its
    private copy the scored bytes written back, and no public copy."""
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=PhotoKind.VERIFICATION,
        raw_key=f"raw/{user.id}/{photo_id}",
        status=status,
        moderation={"provider": "sightengine", "faces": 1}
        if status is ReviewStatus.APPROVED
        else None,
    )
    db.add(photo)
    await db.flush()
    await storage.put_bytes(PRIVATE, photo.raw_key, data or jpeg("olive"), "image/jpeg")
    return photo


async def selfie(
    db: AsyncSession,
    storage: FakeStorage | None,
    user: User,
    *,
    data: bytes | None = None,
) -> Photo:
    """A selfie uploaded (its file in storage, unless `storage` is None) and
    not yet sent."""
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=PhotoKind.SELFIE,
        raw_key=f"raw/{user.id}/{photo_id}",
    )
    db.add(photo)
    await db.flush()
    if storage is not None:
        await storage.put_bytes(
            PRIVATE, photo.raw_key, data or jpeg("salmon"), "image/jpeg"
        )
    return photo


async def submitted(
    db: AsyncSession,
    storage: FakeStorage,
    user: User,
    *,
    data: bytes | None = None,
    created_at: datetime | None = None,
) -> tuple[Verification, Photo]:
    """A verification with its selfie sent, waiting for the worker."""
    photo = await selfie(db, storage, user, data=data)
    verification = Verification(
        user_id=user.id, challenge="none", selfie_photo_id=photo.id
    )
    db.add(verification)
    await db.flush()
    if created_at is not None:
        await db.execute(
            update(Verification)
            .where(Verification.id == verification.id)
            .values(created_at=created_at)
        )
    return verification, photo


async def fresh(db: AsyncSession, model: type[Any], row_id: uuid.UUID) -> Any:
    found = await db.scalar(
        select(model)
        .where(model.id == row_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def start(client: AsyncClient, token: str) -> Response:
    return await client.post("/v1/verification/start", headers=bearer(token))


async def submit(
    client: AsyncClient, token: str, verification_id: object, photo_id: object
) -> Response:
    return await client.post(
        f"/v1/verification/{verification_id}/submit",
        json={"photo_id": str(photo_id)},
        headers=bearer(token),
    )


async def latest(client: AsyncClient, token: str) -> Response:
    return await client.get("/v1/verification/latest", headers=bearer(token))
