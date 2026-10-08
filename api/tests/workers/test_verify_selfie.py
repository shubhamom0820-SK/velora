"""`verify_selfie` (T-4.5): the job around `verification.service.verify`,
which `tests/modules/verification/test_verify.py` covers. Here: what waiting
and failing do. It tries again; its last try records why rather than leave
the person waiting on a comparison that won't come."""

from __future__ import annotations

from typing import Any

import pytest
from arq import Retry
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewStatus
from app.core.providers.facematch import FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.modules.photos.models import Photo
from app.modules.verification.models import Verification
from app.workers.tasks import verify_selfie as job
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import (
    at_selfie,
    face_photo,
    fresh,
    submitted,
)


def _ctx(
    db: AsyncSession, storage: FakeStorage, facematch: FakeFaceMatch, job_try: int
) -> dict[str, Any]:
    return {
        "sessionmaker": Sessions(db),
        "storage": storage,
        "facematch": facematch,
        "queue": FakeQueue(),
        "settings": make_test_settings(),
        "job_try": job_try,
    }


async def test_it_decides_through_the_queue(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)

    result = await job.verify_selfie(
        _ctx(db, storage, facematch, 1), verification_id=str(verification.id)
    )

    assert result == "approved"
    assert (await fresh(db, Photo, selfie.id)).moderation["decided_by"] == "queue"


@pytest.mark.parametrize("job_try", [1, job.VERIFY_TRIES - 1])
async def test_a_failure_is_tried_again(
    db: AsyncSession, make_user: MakeUser, job_try: int
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, _ = await submitted(db, storage, user)
    facematch.next = "fail"

    with pytest.raises(Retry) as retry:
        await job.verify_selfie(
            _ctx(db, storage, facematch, job_try),
            verification_id=str(verification.id),
        )

    assert retry.value.defer_score == 10_000 * job_try
    assert (await fresh(db, Verification, verification.id)).status is (
        ReviewStatus.PENDING
    )


async def test_the_last_failure_is_unavailable_so_she_can_start_again(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)
    facematch.next = "fail"

    result = await job.verify_selfie(
        _ctx(db, storage, facematch, job.VERIFY_TRIES),
        verification_id=str(verification.id),
    )

    assert result == "unavailable"
    assert (await fresh(db, Photo, selfie.id)).reject_reason == "unavailable"
    [failed] = [e for e in captured_logs.events if e["event"] == "verification.failed"]
    assert (failed["log_level"], failed["job_try"], failed["why"]) == (
        "error",
        job.VERIFY_TRIES,
        "RuntimeError",
    )
    assert selfie.raw_key not in captured_logs.text
    captured_logs.assert_listening()


async def test_a_face_photo_still_waiting_at_the_last_try_is_no_photos(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user, status=ReviewStatus.PENDING)
    verification, selfie = await submitted(db, storage, user)

    with pytest.raises(Retry) as retry:
        await job.verify_selfie(
            _ctx(db, storage, facematch, 1), verification_id=str(verification.id)
        )
    assert retry.value.defer_score == 20_000

    result = await job.verify_selfie(
        _ctx(db, storage, facematch, job.VERIFY_TRIES),
        verification_id=str(verification.id),
    )

    assert result == "no_photos"
    assert (await fresh(db, Photo, selfie.id)).reject_reason == "no_photos"


async def test_one_never_submitted_is_left_alone_at_the_last_try(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    verification = Verification(user_id=user.id, challenge="none")
    db.add(verification)
    await db.flush()

    result = await job.verify_selfie(
        _ctx(db, storage, facematch, job.VERIFY_TRIES),
        verification_id=str(verification.id),
    )

    assert result == "never submitted: left as it is"
    assert (await fresh(db, Verification, verification.id)).status is (
        ReviewStatus.PENDING
    )
