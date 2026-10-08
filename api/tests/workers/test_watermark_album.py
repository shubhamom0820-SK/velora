"""`watermark_album` (T-8.4, D-730): the job around `album.service.
sync_copies`, which `tests/modules/album/test_album.py` covers. Here: that it
runs through the queue, and what failing does: tried again, and the last try
logs at error level by the request's id, never a key (rule 15)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from arq import Retry
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.core.providers import FakeProviders
from app.core.providers.storage import FakeStorage
from app.workers.tasks import watermark_album as job
from tests.conftest import CapturedLogs, MakeUser
from tests.modules.album.support import SETTINGS, album_of, asked, decide
from tests.modules.photos.test_moderate import Sessions

pytestmark = pytest.mark.usefixtures("test_redis")


def _ctx(db: AsyncSession, storage: FakeStorage, job_try: int) -> dict[str, Any]:
    return {
        "sessionmaker": Sessions(db),
        "storage": storage,
        "settings": SETTINGS,
        "job_try": job_try,
    }


async def _granted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, storage: FakeStorage
) -> str:
    _, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    await album_of(db, woman, storage, photos=1)
    request = await asked(client, token, woman.id)
    assert (await decide(client, woman_token, request["id"], True)).status_code == 200
    return str(request["id"])


async def test_it_makes_the_copies_through_the_queue(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    storage = fake_providers.storage
    request_id = await _granted(db, client, make_user, storage)

    result = await job.watermark_album(_ctx(db, storage, 1), request_id=request_id)

    assert result == "made 1, deleted 0"
    assert any(key.startswith(f"album/{request_id}/") for _, key in storage.objects)


async def test_a_request_nobody_holds_is_nothing_to_do(
    db: AsyncSession, fake_providers: FakeProviders
) -> None:
    result = await job.watermark_album(
        _ctx(db, fake_providers.storage, 1), request_id=str(uuid.uuid4())
    )

    assert result == "no such request"


async def test_storage_down_is_tried_again_then_logged(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
    captured_logs: CapturedLogs,
) -> None:
    storage = fake_providers.storage
    request_id = await _granted(db, client, make_user, storage)

    async def down(*_: Any) -> bytes:
        raise ConnectionError("storage is down")

    monkeypatch.setattr(storage, "get_bytes", down)

    for job_try in range(1, job.WATERMARK_TRIES):
        with pytest.raises(Retry):
            await job.watermark_album(_ctx(db, storage, job_try), request_id=request_id)
    result = await job.watermark_album(
        _ctx(db, storage, job.WATERMARK_TRIES), request_id=request_id
    )

    assert result == "failed: left as it was"
    assert "album.read_failed" in captured_logs.text
    assert request_id in captured_logs.text
    assert "scored/" not in captured_logs.text and "album/" not in captured_logs.text
