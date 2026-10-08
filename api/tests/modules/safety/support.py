"""What the reports and blocks tests share (T-9.1)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, OnboardingStep, Role, Seeking, UserStatus
from app.core.providers.storage import FakeStorage
from app.core.security import E164, decrypt_phone, make_access_token
from app.modules.account import service as account_service
from app.modules.profiles import repository as profiles_repository
from app.modules.safety.models import Block
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import make_test_settings
from tests.modules.discovery.support import HERE, bearer
from tests.modules.photos.test_moderate import Sessions

SETTINGS = make_test_settings()


async def block(client: AsyncClient, token: str, user_id: uuid.UUID) -> Response:
    return await client.post(
        "/v1/blocks", json={"user_id": str(user_id)}, headers=bearer(token)
    )


async def unblock(client: AsyncClient, token: str, user_id: uuid.UUID) -> Response:
    return await client.delete(f"/v1/blocks/{user_id}", headers=bearer(token))


async def blocked(client: AsyncClient, token: str, user_id: uuid.UUID) -> None:
    response = await block(client, token, user_id)
    assert response.status_code == 201, response.text


async def unblocked(client: AsyncClient, token: str, user_id: uuid.UUID) -> None:
    response = await unblock(client, token, user_id)
    assert response.status_code == 204, response.text


async def report(
    client: AsyncClient, token: str, reported_id: uuid.UUID, **body: Any
) -> Response:
    payload: dict[str, Any] = {
        "reported_id": str(reported_id),
        "reason": "harass",
        "also_block": False,
        **body,
    }
    return await client.post("/v1/reports", json=payload, headers=bearer(token))


async def rows(db: AsyncSession, blocker: uuid.UUID) -> list[Block]:
    """Every block row `blocker` ever made, standing or lifted, oldest first."""
    found = await db.scalars(
        select(Block)
        .where(Block.blocker_id == blocker)
        .order_by(Block.created_at, Block.unblocked_at.nulls_last())
        .execution_options(populate_existing=True)
    )
    return list(found)


def phone_of(user: User) -> E164:
    assert user.phone_enc is not None
    return decrypt_phone(user.phone_enc, SETTINGS)


async def erased(db: AsyncSession, user: User, storage: FakeStorage) -> None:
    """`user` deleted 29 days ago and erased by the real job (D-500, D-503)."""
    user.status = UserStatus.DELETED
    user.deleted_requested_at = clock.now() - timedelta(days=29, hours=1)
    await db.flush()
    erased_now = await account_service.erase_due_accounts(
        Sessions(db),  # type: ignore[arg-type]
        storage=storage,
        settings=SETTINGS,
    )
    assert erased_now == 1
    await db.refresh(user)
    assert user.anonymised_at is not None


async def again_on(
    db: AsyncSession, phone: E164, gender: Gender, *, username: str
) -> tuple[User, str]:
    """A new account on `phone`, as signing up on it after the erasure makes
    one (D-500), onboarded and placed at `HERE` as `person` leaves one."""
    account = await users_service.create_account(db, phone, SETTINGS)
    user, profile = account.user, account.profile
    user.gender = gender
    user.dob = date(clock.now().year - 25, 1, 1)
    user.role = Role.USER
    user.status = UserStatus.ACTIVE
    user.onboarding_step = OnboardingStep.DONE
    user.is_verified = gender is Gender.FEMALE
    profile.first_name = "Again"
    profile.username = username
    profile.about = "A test profile, with an about long enough for the rules."
    profile.city = "Phagwara"
    profile.seeking = Seeking.WOMEN if gender is Gender.MALE else Seeking.MEN
    profile.location = profiles_repository.point(*HERE)
    profile.completeness = 50
    await db.flush()
    await db.refresh(user)
    token = make_access_token(user.id, user.role, SETTINGS, auth_time=clock.now())
    return user, token
