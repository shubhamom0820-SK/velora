"""`match_photo` (T-4.12, D-393): the job around
`verification.service.match_photo`, which `tests/modules/verification/
test_badge.py` covers. Here: that it decides through the queue, and what
failing does: tried again, and the last try leaves the photo as it is."""

from __future__ import annotations

from typing import Any

import pytest
from arq import Retry
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers.facematch import FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.modules.photos.models import Photo
from app.workers.tasks import match_photo as job
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import approved_photo, at_selfie, fresh
from tests.modules.verification.test_badge import _kept


def _ctx(
    db: AsyncSession, storage: FakeStorage, facematch: FakeFaceMatch, job_try: int
) -> dict[str, Any]:
    return {
        "sessionmaker": Sessions(db),
        "storage": storage,
        "facematch": facematch,
        "settings": make_test_settings(),
        "job_try": job_try,
    }


async def test_it_decides_through_the_queue(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)

    result = await job.match_photo(
        _ctx(db, storage, facematch, 1), photo_id=str(photo.id)
    )

    assert result == "matched"
    record = (await fresh(db, Photo, photo.id)).moderation["selfie_match"]
    assert (record["decided_by"], record["matched"]) == ("queue", True)


@pytest.mark.parametrize("job_try", [1, job.MATCH_TRIES - 1])
async def test_storage_down_is_tried_again(
    db: AsyncSession,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
    job_try: int,
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)

    async def down(*args: object, **kwargs: object) -> bytes:
        raise ConnectionError("storage is down")

    monkeypatch.setattr(storage, "read_prefix", down)

    with pytest.raises(Retry) as retry:
        await job.match_photo(
            _ctx(db, storage, facematch, job_try), photo_id=str(photo.id)
        )

    assert retry.value.defer_score == 10_000 * job_try
    assert "selfie_match" not in (await fresh(db, Photo, photo.id)).moderation


async def test_the_last_failure_logs_an_error_and_leaves_the_photo_as_it_is(
    db: AsyncSession,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
    captured_logs: CapturedLogs,
) -> None:
    """The badge rests on comparisons that were made, never on one that
    wasn't; the sweep that would pick this up later is P-300."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    _, shot = await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)

    async def down(*args: object, **kwargs: object) -> bytes:
        raise ConnectionError("storage is down")

    monkeypatch.setattr(storage, "read_prefix", down)

    result = await job.match_photo(
        _ctx(db, storage, facematch, job.MATCH_TRIES), photo_id=str(photo.id)
    )

    assert result == "failed: left as it was"
    decided = await fresh(db, Photo, photo.id)
    assert decided.status.value == "approved"
    assert "selfie_match" not in decided.moderation
    [failed] = [
        e for e in captured_logs.events if e["event"] == "verification.storage_failed"
    ]
    assert (failed["log_level"], failed["job_try"]) == ("error", job.MATCH_TRIES)
    assert shot.raw_key not in captured_logs.text
    captured_logs.assert_listening()
