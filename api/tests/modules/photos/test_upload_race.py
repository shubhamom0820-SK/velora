"""Two upload URLs asked for at once (T-4.2): the user's row is locked first,
so the places are counted one request at a time.

Private photos have no constraint in the database (only the service counts
them), so without the lock two requests could each count five and make seven.
What is asserted is what the lock decides, as `test_race.py` does (`f543b0d`):
both requests reach the lock together, and each, once it holds the user, waits
for the other and records whether it waited alone.

Committed for real, on a fresh man, never deleted (tests/committed.py).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep, PhotoKind
from app.core.errors import AppError
from app.core.providers.storage import FakeStorage
from app.modules.photos import service
from app.modules.photos.models import Photo
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.committed import fresh_man
from tests.conftest import make_test_settings

ARRIVE_WAIT_S = 5.0
COMPANY_WAIT_S = 0.5


async def _man_with_five_private_photos(engine: AsyncEngine) -> uuid.UUID:
    man = await fresh_man(engine)
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.PHOTOS)
        )
        for _ in range(5):
            photo_id = uuid.uuid4()
            session.add(
                Photo(
                    id=photo_id,
                    user_id=man,
                    kind=PhotoKind.PRIVATE,
                    raw_key=f"raw/{man}/{photo_id}",
                )
            )
    return man


async def test_two_requests_for_the_last_private_place_get_one(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    man = await _man_with_five_private_photos(test_engine)
    arrived: list[int] = []
    all_arrived = asyncio.Event()
    holding: set[int] = set()
    company = asyncio.Event()
    waited_alone: list[bool] = []
    real_lock = users_service.locked_user

    async def arrive_together_then_lock(session: AsyncSession, user_id: Any) -> User:
        arrived.append(1)
        if len(arrived) == 2:
            all_arrived.set()
        await asyncio.wait_for(all_arrived.wait(), ARRIVE_WAIT_S)
        user = await real_lock(session, user_id)
        me = id(asyncio.current_task())
        holding.add(me)
        if len(holding) > 1:
            company.set()
        try:
            await asyncio.wait_for(company.wait(), COMPANY_WAIT_S)
            waited_alone.append(False)
        except TimeoutError:
            waited_alone.append(True)
        finally:
            holding.discard(me)
        return user

    monkeypatch.setattr(users_service, "locked_user", arrive_together_then_lock)

    async def ask() -> object:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await session.get(User, man)
            assert user is not None
            await session.commit()  # as `current_user` ends its read
            try:
                return await service.upload_url(
                    session,
                    user,
                    kind=PhotoKind.PRIVATE,
                    position=None,
                    content_type="image/jpeg",
                    storage=FakeStorage(),
                    settings=make_test_settings(),
                )
            except AppError as error:
                return error.code

    results = await asyncio.gather(ask(), ask())

    assert len(arrived) == 2  # the overlap was forced
    assert waited_alone == [True, True]  # what the lock decided
    assert sorted(
        str(type(r).__name__) if not isinstance(r, str) else r for r in results
    ) == [
        "NOT_ALLOWED",
        "UploadUrl",
    ]
