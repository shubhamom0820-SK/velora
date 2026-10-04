"""Moderation's decision and the owner's reorder at once (T-4.4): the job locks
the user's row first, as every photo change does, so the two take turns.

Without that, the reorder reads the photo as pending, waits on the photo's row
while the job approves it, then writes "pending" back over "approved": an
approved photo, published, that its row says is still waiting. The overlap is
forced and observed, not hoped for: the job stops holding its locks, the reorder
starts, and the test sees Postgres make it wait before letting the job go on.

Committed for real, on a fresh man, never deleted (tests/committed.py).
"""

from __future__ import annotations

import asyncio
import io
import uuid
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers.moderation import FakeModeration
from app.core.providers.storage import FakeStorage
from app.modules.photos import repository, service
from app.modules.photos.models import Photo
from app.modules.users.models import User
from tests.committed import fresh_man
from tests.conftest import make_test_settings

HOLD_WAIT_S = 5.0
BLOCKED_WAIT_S = 3.0


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (400, 300), "olive").save(out, "JPEG")
    return out.getvalue()


async def _two_public_photos(
    engine: AsyncEngine, storage: FakeStorage
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A man at the photos step: an approved photo at 0, a pending one at 1."""
    man = await fresh_man(engine)
    approved, pending = uuid.uuid4(), uuid.uuid4()
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.PHOTOS)
        )
        for photo_id, position, status in (
            (approved, 0, ReviewStatus.APPROVED),
            (pending, 1, ReviewStatus.PENDING),
        ):
            session.add(
                Photo(
                    id=photo_id,
                    user_id=man,
                    kind=PhotoKind.PUBLIC,
                    position=position,
                    raw_key=f"raw/{man}/{photo_id}",
                    status=status,
                )
            )
    await storage.put_bytes(
        "velora-private", f"raw/{man}/{pending}", _jpeg(), "image/jpeg"
    )
    return man, approved, pending


async def _waiting_on_a_lock(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        waiting = await connection.scalar(
            text(
                "select count(*) from pg_stat_activity "
                "where datname = current_database() and wait_event_type = 'Lock'"
            )
        )
    return int(waiting or 0)


async def test_the_decision_and_a_reorder_take_turns(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = FakeStorage()
    settings = make_test_settings()
    man, approved, pending = await _two_public_photos(test_engine, storage)
    holding, release = asyncio.Event(), asyncio.Event()
    real = repository.photo_for_update

    async def hold_then_lock(session: AsyncSession, user_id: Any, photo_id: Any) -> Any:
        photo = await real(session, user_id, photo_id)
        holding.set()
        await asyncio.wait_for(release.wait(), HOLD_WAIT_S)
        return photo

    monkeypatch.setattr(repository, "photo_for_update", hold_then_lock)

    def sessions() -> AsyncSession:
        return AsyncSession(test_engine, expire_on_commit=False)

    async def moderate() -> str:
        return await service.moderate(
            sessions,
            pending,
            storage=storage,
            moderation=FakeModeration(),
            settings=settings,
        )

    async def reorder() -> object:
        async with sessions() as session:
            user = await session.get(User, man)
            assert user is not None
            await session.commit()
            return await service.reorder(
                session, user, [pending, approved], storage=storage, settings=settings
            )

    job = asyncio.create_task(moderate())
    await asyncio.wait_for(holding.wait(), HOLD_WAIT_S)
    owner = asyncio.create_task(reorder())
    blocked = 0
    for _ in range(int(BLOCKED_WAIT_S / 0.05)):
        blocked = await _waiting_on_a_lock(test_engine)
        if blocked:
            break
        await asyncio.sleep(0.05)
    release.set()
    outcome, _ = await asyncio.gather(job, owner)

    assert blocked == 1  # the overlap was forced: the reorder waited on a lock
    assert outcome == "approved"
    async with AsyncSession(test_engine) as session:
        rows = {
            photo.id: (photo.status, photo.position, photo.public_key)
            for photo in await session.scalars(
                select(Photo).where(Photo.user_id == man)
            )
        }
    assert rows == {
        pending: (ReviewStatus.APPROVED, 0, f"p/{pending}.jpg"),
        approved: (ReviewStatus.APPROVED, 1, None),
    }
