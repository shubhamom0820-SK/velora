"""What discovery's tests share: people placed on the grid, their photos, and
the request."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FraudBand, Gender, PhotoKind, ReviewStatus, Seeking
from app.modules.onboarding import rules as onboarding_rules
from app.modules.photos.models import Photo
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile
from app.modules.safety.models import FraudScore
from app.modules.users.models import User
from tests.conftest import MakeUser

# Phagwara's middle, a grid point (D-490). One grid step north is 0.01°, about
# 1.11 km.
HERE = (31.22, 75.77)
STEP_KM = 1.112


def north(steps: float) -> tuple[float, float]:
    """`steps` grid steps due north of `HERE`."""
    return (round(HERE[0] + 0.01 * steps, 6), HERE[1])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def error(response: Response) -> dict[str, Any]:
    found: dict[str, Any] = response.json()["error"]
    return found


async def person(
    db: AsyncSession,
    make_user: MakeUser,
    gender: Gender | str = Gender.FEMALE,
    *,
    at: tuple[float, float] = HERE,
    seeking: Seeking | None = None,
    verified: bool | None = None,
    completeness: int = 50,
    last_active_at: datetime | None = None,
    created_at: datetime | None = None,
    **profile: Any,
) -> tuple[User, str]:
    """Someone onboarded and placed at `at`, its grid point as the API
    stores it, at `completeness` (50, as finishing with no photo or one leaves
    it). `profile` sets any other profile column."""
    user, token = await make_user(gender, verified=verified)
    row = await db.get(Profile, user.id)
    assert row is not None
    row.location = profiles_repository.point(*at)
    row.completeness = completeness
    if seeking is not None:
        row.seeking = seeking
    for column, value in profile.items():
        setattr(row, column, value)
    if last_active_at is not None:
        user.last_active_at = last_active_at
    if created_at is not None:
        user.created_at = created_at
    await db.flush()
    return user, token


async def banded(db: AsyncSession, user: User, band: FraudBand) -> None:
    db.add(FraudScore(user_id=user.id, score=50, band=band))
    await db.flush()


async def photo(
    db: AsyncSession,
    user: User,
    *,
    place: int | None = 0,
    kind: PhotoKind = PhotoKind.PUBLIC,
    status: ReviewStatus = ReviewStatus.APPROVED,
    matched: bool | None = None,
    scored: bool = True,
) -> Photo:
    """A photo as moderation leaves one: an approved public one with its public
    copy, an approved private one with its scored copy (D-700) unless `scored`
    is False, as one approved before D-700 is; `matched`, its badge
    comparison's result (D-393), if one was made."""
    photo_id = uuid.uuid4()
    public = kind is PhotoKind.PUBLIC and status is ReviewStatus.APPROVED
    private = kind is PhotoKind.PRIVATE and status is ReviewStatus.APPROVED
    moderation: dict[str, Any] = {"provider": "sightengine", "faces": 1}
    if matched is not None:
        moderation["selfie_match"] = {"matched": matched, "decided_by": "seed"}
    row = Photo(
        id=photo_id,
        user_id=user.id,
        kind=kind,
        position=place if kind is PhotoKind.PUBLIC else None,
        raw_key=f"raw/{user.id}/{photo_id}",
        public_key=f"p/{photo_id}.jpg" if public else None,
        scored_key=f"scored/{user.id}/{photo_id}.jpg" if private and scored else None,
        status=status,
        moderation=moderation,
    )
    db.add(row)
    await db.flush()
    return row


async def finished_with(db: AsyncSession, user: User, approved: int) -> None:
    """The completeness finishing gives `approved` photos (D-310)."""
    row = await db.get(Profile, user.id)
    assert row is not None
    row.completeness = onboarding_rules.completeness(approved)
    await db.flush()


async def discover(client: AsyncClient, token: str, **params: Any) -> Response:
    return await client.get("/v1/discover", params=params, headers=bearer(token))


async def ids(client: AsyncClient, token: str, **params: Any) -> list[str]:
    """Every id the feed gives, in order, one page of 50."""
    response = await discover(client, token, limit=50, **params)
    assert response.status_code == 200, response.text
    return [card["id"] for card in response.json()["items"]]


async def block(db: AsyncSession, blocker: User, blocked: User) -> None:
    await db.execute(
        text("INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)"),
        {"a": blocker.id, "b": blocked.id},
    )


async def swipe(db: AsyncSession, swiper: User, target: User, direction: str) -> None:
    await db.execute(
        text(
            "INSERT INTO swipes (swiper_id, target_id, dir) VALUES (:a, :b, "
            "CAST(:dir AS swipe_dir_t))"
        ),
        {"a": swiper.id, "b": target.id, "dir": direction},
    )
