"""`delete_files` (D-078 in D-090's order, T-4.2): a refusal's files, deleted
only once the user is gone, and each deletion read back, never assumed."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers.storage import FakeStorage, ObjectNotFound, S3Storage
from app.core.queue import DELETE_FILES, FakeQueue
from app.workers.tasks import delete_files as job
from tests.conftest import CapturedLogs, MakeUser
from tests.core.test_storage import local_s3_settings
from tests.infra import S3_DOWN_REASON, S3_UP, in_ci, infra_policy

PUBLIC, PRIVATE = "velora-public", "velora-private"
BANNED_ID = str(uuid.uuid4())


class SharedSession:
    """A sessionmaker that hands the job the test's own session, rolled back
    with the test, and leaves closing it to the `db` fixture."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def __call__(self) -> SharedSession:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *exc: object) -> None:
        return None


async def _stored(storage: Any, *objects: tuple[str, str]) -> list[list[str]]:
    for bucket, key in objects:
        await storage.put_bytes(bucket, key, b"photo", "image/jpeg")
    return [[bucket, key] for bucket, key in objects]


def _ctx(db: AsyncSession, storage: Any, queue: FakeQueue) -> dict[str, Any]:
    return {"sessionmaker": SharedSession(db), "storage": storage, "queue": queue}


async def _run(
    db: AsyncSession,
    storage: Any,
    queue: FakeQueue,
    user_id: str,
    objects: list[list[str]],
    **kw: Any,
) -> str:
    return await job.delete_files(
        _ctx(db, storage, queue),
        user_id=user_id,
        banned_id=BANNED_ID,
        objects=objects,
        **kw,
    )


async def test_a_refused_users_files_are_deleted_and_read_back_gone(
    db: AsyncSession, captured_logs: CapturedLogs
) -> None:
    storage, queue = FakeStorage(), FakeQueue()
    gone = str(uuid.uuid4())  # no such user: the refusal committed
    objects = await _stored(storage, (PRIVATE, f"raw/{gone}/a"), (PUBLIC, "p/a.jpg"))

    result = await _run(db, storage, queue, gone, objects)

    assert result == "deleted"
    assert storage.objects == {}
    assert queue.jobs == []
    done = [e for e in captured_logs.events if e["event"] == "storage.files_deleted"]
    assert [(e["banned_id"], e["files"]) for e in done] == [(BANNED_ID, 2)]
    captured_logs.assert_listening()


async def test_a_user_still_there_is_asked_about_again_not_deleted(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, queue = FakeStorage(), FakeQueue()
    user, _ = await make_user()
    objects = await _stored(storage, (PRIVATE, f"raw/{user.id}/a"))

    result = await _run(db, storage, queue, str(user.id), objects)

    assert result == "the user is still there: asking again"
    assert len(storage.objects) == 1
    [again] = queue.named(DELETE_FILES)
    assert again.defer_by == timedelta(minutes=4)
    assert again.kwargs["check"] == 2


async def test_still_there_at_the_second_check_means_rolled_back_and_nothing_goes(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    """The guard that keeps a photo of someone who was never refused."""
    storage, queue = FakeStorage(), FakeQueue()
    user, _ = await make_user()
    objects = await _stored(storage, (PRIVATE, f"raw/{user.id}/a"))

    result = await _run(db, storage, queue, str(user.id), objects, check=2)

    assert result == "the refusal rolled back: nothing deleted"
    assert len(storage.objects) == 1
    assert queue.jobs == []
    assert any(e["event"] == "storage.delete_skipped" for e in captured_logs.events)


class _DeleteThatDoesntDelete(FakeStorage):
    """Answers success, and deletes nothing: the case a read-back exists for."""

    async def delete(self, bucket: str, key: str) -> None:
        return None


async def test_a_delete_that_answers_success_but_leaves_the_object_is_caught(
    db: AsyncSession,
) -> None:
    """D-090: a delete returning success is not proof the object left. The
    read-back finds it, and the job tries again."""
    storage, queue = _DeleteThatDoesntDelete(), FakeQueue()
    gone = str(uuid.uuid4())
    objects = await _stored(storage, (PRIVATE, f"raw/{gone}/a"))

    result = await _run(db, storage, queue, gone, objects)

    assert result == "some are still there: trying again"
    [again] = queue.named(DELETE_FILES)
    assert (again.kwargs["delete_try"], again.defer_by) == (2, timedelta(minutes=1))


async def test_the_last_try_logs_an_error_naming_only_the_refusal(
    db: AsyncSession, captured_logs: CapturedLogs
) -> None:
    storage, queue = _DeleteThatDoesntDelete(), FakeQueue()
    gone = str(uuid.uuid4())
    key = f"raw/{gone}/a"
    objects = await _stored(storage, (PRIVATE, key))

    result = await _run(db, storage, queue, gone, objects, delete_try=job.DELETE_TRIES)

    assert result == "failed"
    assert queue.jobs == []
    failed = [e for e in captured_logs.events if e["event"] == "storage.delete_failed"]
    assert [(e["log_level"], e["banned_id"], e["remaining"]) for e in failed] == [
        ("error", BANNED_ID, 1)
    ]
    # Rule 15: the refusal's id is enough to find it; never a key or a user.
    assert key not in captured_logs.text
    assert gone not in captured_logs.text
    captured_logs.assert_listening()


class _StorageDown(FakeStorage):
    async def delete(self, bucket: str, key: str) -> None:
        raise ConnectionError("storage is down")

    async def head(self, bucket: str, key: str) -> Any:
        raise ConnectionError("storage is down")


async def test_storage_that_cant_answer_counts_as_not_gone(db: AsyncSession) -> None:
    storage, queue = _StorageDown(), FakeQueue()
    gone = str(uuid.uuid4())
    objects = [[PRIVATE, f"raw/{gone}/a"]]

    result = await _run(db, storage, queue, gone, objects)

    assert result == "some are still there: trying again"
    assert queue.named(DELETE_FILES)[0].kwargs["delete_try"] == 2


@pytest.fixture
async def local_s3() -> AsyncIterator[S3Storage]:
    decision = infra_policy(reachable=S3_UP, ci=in_ci())
    if decision == "skip":
        pytest.skip(S3_DOWN_REASON)
    if decision == "fail":
        pytest.fail(
            f"CI requires the local S3, and it is not reachable ({S3_DOWN_REASON})."
        )
    s3 = S3Storage(local_s3_settings())
    try:
        yield s3
    finally:
        await s3.aclose()


async def test_against_real_s3_the_objects_are_really_gone(
    db: AsyncSession, local_s3: S3Storage
) -> None:
    gone = str(uuid.uuid4())
    objects = await _stored(
        local_s3, (PRIVATE, f"test/{gone}/raw"), (PUBLIC, f"test/{gone}/p.jpg")
    )

    result = await _run(db, local_s3, FakeQueue(), gone, objects)

    assert result == "deleted"
    for bucket, key in objects:
        with pytest.raises(ObjectNotFound):
            await local_s3.head(bucket, key)
