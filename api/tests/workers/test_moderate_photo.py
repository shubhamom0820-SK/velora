"""`moderate_photo` (T-4.4): the job around `photos.service.moderate`, which
`tests/modules/photos/test_moderate.py` covers. Here: what a failure does. Two
tries more, 20 and 40 seconds on; the third failure logs at error level and
leaves the photo pending."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from arq import Retry
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewStatus
from app.core.providers.moderation import FakeModeration
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.workers.tasks import moderate_photo as job
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions, _fresh, _pending


async def _ctx(
    db: AsyncSession, moderation: FakeModeration, storage: FakeStorage, job_try: int
) -> dict[str, Any]:
    return {
        "sessionmaker": Sessions(db),
        "storage": storage,
        "moderation": moderation,
        "queue": FakeQueue(),
        "settings": make_test_settings(),
        "job_try": job_try,
    }


@pytest.mark.parametrize(("job_try", "wait"), [(1, 20), (2, 40)])
async def test_a_failure_is_tried_again_later(
    db: AsyncSession, make_user: MakeUser, job_try: int, wait: int
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    moderation.next = "fail"
    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    with pytest.raises(Retry) as retry:
        await job.moderate_photo(
            await _ctx(db, moderation, storage, job_try),
            photo_id=str(photo.id),
            image_type="image/jpeg",
        )
    assert retry.value.defer_score == wait * 1000
    assert job.FIRST_RETRY_IN * 2 ** (job_try - 1) == timedelta(seconds=wait)


async def test_the_third_failure_logs_an_error_and_leaves_the_photo_pending(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    moderation.next = "fail"
    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    result = await job.moderate_photo(
        await _ctx(db, moderation, storage, job.MODERATE_TRIES),
        photo_id=str(photo.id),
        image_type="image/jpeg",
    )

    assert result == "failed: left as it was"
    assert (await _fresh(db, photo.id)).status is ReviewStatus.PENDING
    [failed] = [
        e for e in captured_logs.events if e["event"] == "moderation.failed_photo"
    ]
    assert (failed["log_level"], failed["photo_id"], failed["job_try"]) == (
        "error",
        str(photo.id),
        3,
    )
    assert photo.raw_key not in captured_logs.text
    captured_logs.assert_listening()


async def test_a_photo_that_isnt_there_is_nothing_to_do(db: AsyncSession) -> None:
    result = await job.moderate_photo(
        await _ctx(db, FakeModeration(), FakeStorage(), 1),
        photo_id=str(uuid.uuid4()),
    )

    assert result.startswith("no such photo")
