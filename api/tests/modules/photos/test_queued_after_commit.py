"""An approval's blur (D-543) and badge comparison (D-393) are queued only once
it is committed (P-962). Queued inside moderation's transaction, a worker fast
enough read the photo as still pending, answered "nothing to blur", and
finished for good under the job's fixed id: seen in CI run 39310142086.

The queue here runs each job the moment it is queued, the fastest any worker
could be, on connections of its own, so each reads only what was committed.
Committed for real, on a fresh man; his photos and verification are taken back
at the end (tests/committed.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import build_sessionmaker
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers.facematch import FakeFaceMatch
from app.core.providers.moderation import FakeModeration
from app.core.providers.storage import FakeStorage
from app.core.queue import BLUR_PHOTO, MATCH_PHOTO, FakeQueue, QueuedJob
from app.modules.photos import service
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification import service as verification_service
from app.modules.verification.models import Verification
from tests.committed import fresh_man
from tests.conftest import make_test_settings
from tests.modules.verification.support import PRIVATE, PUBLIC, jpeg
from tests.modules.verification.test_race import forget_photos


@dataclass
class RunsAtOnce(FakeQueue):
    """Runs each job inside `enqueue`, before it returns, and keeps what it
    answered by job id. A job id already queued isn't run again, as ARQ's
    isn't queued again."""

    run: Callable[[QueuedJob], Awaitable[str]] | None = None
    ran: dict[str | None, str] = field(default_factory=dict)

    async def enqueue(
        self,
        job: str,
        *,
        job_id: str | None = None,
        defer_by: timedelta | None = None,
        **kwargs: Any,
    ) -> None:
        before = len(self.jobs)
        await super().enqueue(job, job_id=job_id, defer_by=defer_by, **kwargs)
        if len(self.jobs) > before:
            assert self.run is not None
            self.ran[job_id] = await self.run(self.jobs[-1])


async def _verified_with_a_pending_photo(
    engine: AsyncEngine, storage: FakeStorage
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A man whose selfie matched (`is_verified`, his verification and selfie
    approved, his face photo approved), with a public photo waiting for
    moderation."""
    man = await fresh_man(engine)
    face, shot, pending = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    verification_id = uuid.uuid4()
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.PHOTOS, is_verified=True)
        )
        session.add_all(
            [
                Photo(
                    id=face,
                    user_id=man,
                    kind=PhotoKind.VERIFICATION,
                    raw_key=f"raw/{man}/{face}",
                    status=ReviewStatus.APPROVED,
                    moderation={"faces": 1},
                ),
                Photo(
                    id=shot,
                    user_id=man,
                    kind=PhotoKind.SELFIE,
                    raw_key=f"raw/{man}/{shot}",
                    status=ReviewStatus.APPROVED,
                ),
                Photo(
                    id=pending,
                    user_id=man,
                    kind=PhotoKind.PUBLIC,
                    position=0,
                    raw_key=f"raw/{man}/{pending}",
                ),
            ]
        )
        await session.flush()
        session.add(
            Verification(
                id=verification_id,
                user_id=man,
                challenge="none",
                selfie_photo_id=shot,
                status=ReviewStatus.APPROVED,
            )
        )
    for photo_id, colour in ((face, "olive"), (shot, "salmon"), (pending, "navy")):
        await storage.put_bytes(
            PRIVATE, f"raw/{man}/{photo_id}", jpeg(colour), "image/jpeg"
        )
    return man, pending, verification_id


async def test_a_job_run_the_moment_it_is_queued_still_blurs_and_compares(
    test_engine: AsyncEngine,
) -> None:
    storage, settings = FakeStorage(), make_test_settings()
    sessions = build_sessionmaker(test_engine)
    man, photo_id, verification_id = await _verified_with_a_pending_photo(
        test_engine, storage
    )

    async def run(queued: QueuedJob) -> str:
        photo = uuid.UUID(queued.kwargs["photo_id"])
        if queued.job == BLUR_PHOTO:
            return await service.blur(
                sessions, photo, storage=storage, settings=settings
            )
        if queued.job == MATCH_PHOTO:
            return await verification_service.match_photo(
                sessions,
                photo,
                storage=storage,
                facematch=FakeFaceMatch(),
                settings=settings,
            )
        raise AssertionError(f"moderation queued {queued.job}")

    queue = RunsAtOnce(run=run)
    try:
        outcome = await service.moderate(
            sessions,
            photo_id,
            storage=storage,
            moderation=FakeModeration(),
            queue=queue,
            settings=settings,
        )

        assert outcome == "approved"
        assert queue.ran == {
            f"match_photo:{photo_id}": "matched",
            f"blur_photo:{photo_id}": "blurred",
        }
        async with AsyncSession(test_engine) as session:
            photo = await session.get(Photo, photo_id)
        assert photo is not None
        assert photo.status is ReviewStatus.APPROVED
        assert photo.blur_key is not None
        assert (PUBLIC, photo.blur_key) in storage.objects
        assert photo.moderation is not None
        match = photo.moderation["selfie_match"]
        assert (match["verification_id"], match["matched"]) == (
            str(verification_id),
            True,
        )
    finally:
        await forget_photos(test_engine, man)
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(
                update(User).where(User.id == man).values(is_verified=False)
            )
