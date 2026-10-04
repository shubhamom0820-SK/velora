"""A wake and the queued job comparing the same selfie at once (D-261): the
decision is written once. Two transactions on two connections, so on rows
committed for real (06-TESTING, "Tests that commit rows"), each assertion
scoped to this test's ids."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import build_sessionmaker
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification import service
from app.modules.verification.models import Verification
from tests.committed import fresh_man
from tests.conftest import CapturedLogs, make_test_settings
from tests.modules.verification.support import PRIVATE, PUBLIC, jpeg


class BothInside(FakeFaceMatch):
    """Holds each comparison until two are inside at once: the overlap is
    forced, never hoped for. Times out rather than hang if only one comes."""

    def __init__(self) -> None:
        super().__init__()
        self.barrier = asyncio.Barrier(2)
        self.inside = 0

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        self.inside += 1
        async with asyncio.timeout(10):
            await self.barrier.wait()
        return await super().compare(selfie, references)


async def _committed_selfie(
    engine: AsyncEngine, storage: FakeStorage
) -> tuple[uuid.UUID, uuid.UUID]:
    man = await fresh_man(engine)
    photo_id, selfie_id, verification_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.SELFIE)
        )
        session.add_all(
            [
                Photo(
                    id=photo_id,
                    user_id=man,
                    kind=PhotoKind.PUBLIC,
                    position=0,
                    raw_key=f"raw/{man}/{photo_id}",
                    public_key=f"p/{photo_id}.jpg",
                    status=ReviewStatus.APPROVED,
                ),
                Photo(
                    id=selfie_id,
                    user_id=man,
                    kind=PhotoKind.SELFIE,
                    raw_key=f"raw/{man}/{selfie_id}",
                ),
            ]
        )
        await session.flush()
        session.add(
            Verification(
                id=verification_id,
                user_id=man,
                challenge="none",
                selfie_photo_id=selfie_id,
            )
        )
    await storage.put_bytes(PUBLIC, f"p/{photo_id}.jpg", jpeg("navy"), "image/jpeg")
    await storage.put_bytes(PRIVATE, f"raw/{man}/{selfie_id}", jpeg(), "image/jpeg")
    return man, verification_id


async def test_a_wake_and_the_job_at_once_decide_it_once(
    test_engine: AsyncEngine, captured_logs: CapturedLogs
) -> None:
    storage, facematch = FakeStorage(), BothInside()
    man, verification_id = await _committed_selfie(test_engine, storage)
    sessions = build_sessionmaker(test_engine)

    async def run(via: str) -> str:
        return await service.verify(
            sessions,
            verification_id,
            storage=storage,
            facematch=facematch,
            settings=make_test_settings(),
            via=via,
        )

    outcomes = await asyncio.gather(run("wake"), run("queue"))

    # Both were inside the comparison together, so both reached the write.
    assert facematch.inside == 2
    assert sorted(outcomes) == [
        "approved",
        "approved while it was compared: left as it is",
    ]
    decided = [e for e in captured_logs.events if e["event"] == "verification.decided"]
    assert [e["verification_id"] for e in decided] == [str(verification_id)]
    async with AsyncSession(test_engine) as session:
        verification = await session.get(Verification, verification_id)
        user = await session.get(User, man)
    assert verification is not None and user is not None
    assert (verification.status, user.is_verified) == (ReviewStatus.APPROVED, True)
