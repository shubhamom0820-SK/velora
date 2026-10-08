"""`photos.service.blur`, the `blur_photo` job's work (T-6.7, D-543): an
approved public photo's blurred copy, in the public bucket under a key of its
own, recorded only while the photo is still what was read; and queued when a
public photo is approved."""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PhotoKind, ReviewStatus
from app.core.providers.moderation import FakeModeration
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.modules.photos import service
from app.modules.photos.models import Photo
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions

PUBLIC, PRIVATE = "velora-public", "velora-private"


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (800, 600), "teal").save(out, "JPEG")
    return out.getvalue()


async def _approved(
    db: AsyncSession,
    storage: FakeStorage,
    user: User,
    *,
    kind: PhotoKind = PhotoKind.PUBLIC,
    status: ReviewStatus = ReviewStatus.APPROVED,
) -> Photo:
    photo_id = uuid.uuid4()
    public = kind is PhotoKind.PUBLIC and status is ReviewStatus.APPROVED
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=kind,
        position=0 if kind is PhotoKind.PUBLIC else None,
        raw_key=f"raw/{user.id}/{photo_id}",
        public_key=f"p/{photo_id}.jpg" if public else None,
        status=status,
    )
    db.add(photo)
    await db.flush()
    if public:
        await storage.put_bytes(PUBLIC, f"p/{photo_id}.jpg", _jpeg(), "image/jpeg")
    return photo


async def _blur(db: AsyncSession, photo: Photo, storage: FakeStorage) -> str:
    return await service.blur(
        Sessions(db), photo.id, storage=storage, settings=make_test_settings()
    )


async def _fresh(db: AsyncSession, photo_id: uuid.UUID) -> Photo:
    found = await db.scalar(
        select(Photo)
        .where(Photo.id == photo_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def test_an_approved_public_photo_gets_a_blur_under_a_key_of_its_own(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _approved(db, storage, user)

    assert await _blur(db, photo, storage) == "blurred"

    after = await _fresh(db, photo.id)
    assert after.blur_key is not None
    assert after.blur_key.startswith("b/")
    # Never the photo's id: `p/{id}.jpg` is the photo itself.
    assert str(photo.id) not in after.blur_key
    stored = storage.objects[(PUBLIC, after.blur_key)]
    assert stored.data != storage.objects[(PUBLIC, f"p/{photo.id}.jpg")].data


async def test_a_second_run_changes_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _approved(db, storage, user)
    await _blur(db, photo, storage)
    first = (await _fresh(db, photo.id)).blur_key

    assert await _blur(db, photo, storage) == "nothing to blur"
    assert (await _fresh(db, photo.id)).blur_key == first
    assert (
        len([k for (b, k) in storage.objects if b == PUBLIC and k.startswith("b/")])
        == 1
    )


async def test_only_an_approved_public_photo_is_blurred(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await make_user()
    for kind, status in (
        (PhotoKind.PRIVATE, ReviewStatus.APPROVED),
        (PhotoKind.VERIFICATION, ReviewStatus.APPROVED),
        (PhotoKind.PUBLIC, ReviewStatus.PENDING),
        (PhotoKind.PUBLIC, ReviewStatus.REJECTED),
    ):
        photo = await _approved(db, storage, user, kind=kind, status=status)
        assert await _blur(db, photo, storage) == "nothing to blur"
        assert (await _fresh(db, photo.id)).blur_key is None
    assert not [k for (b, k) in storage.objects if k.startswith("b/")]


async def test_a_photo_removed_while_it_was_blurred_keeps_no_blur(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Its owner removed it between the read and the write: the file just
    written is deleted, never left behind with no row naming it."""
    user, _ = await make_user()

    class _RemovedMeanwhile(FakeStorage):
        async def get_bytes(self, bucket: str, key: str) -> bytes:
            data = await super().get_bytes(bucket, key)
            row = await db.get(Photo, photo.id)
            assert row is not None
            row.status, row.reject_reason = ReviewStatus.REJECTED, "user_deleted"
            await db.flush()
            return data

    storage = _RemovedMeanwhile()
    photo = await _approved(db, storage, user)

    assert (
        await _blur(db, photo, storage)
        == "changed while it was blurred: its blur removed"
    )
    assert (await _fresh(db, photo.id)).blur_key is None
    assert not [k for (b, k) in storage.objects if k.startswith("b/")]


async def test_approving_a_public_photo_queues_its_blur(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation, queue = FakeStorage(), FakeModeration(), FakeQueue()
    user, _ = await make_user()
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=PhotoKind.PUBLIC,
        position=0,
        raw_key=f"raw/{user.id}/{photo_id}",
    )
    db.add(photo)
    await db.flush()
    await storage.put_bytes(PRIVATE, photo.raw_key, _jpeg(), "image/jpeg")

    await service.moderate(
        Sessions(db),
        photo_id,
        storage=storage,
        moderation=moderation,
        queue=queue,
        settings=make_test_settings(),
    )

    assert [(job.job_id, job.kwargs) for job in queue.named("blur_photo")] == [
        (f"blur_photo:{photo_id}", {"photo_id": str(photo_id)})
    ]


async def test_removing_a_photo_removes_its_blur(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-543: the blur goes with the photo, never left in the public bucket."""
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _approved(db, storage, user)
    await _blur(db, photo, storage)
    blur_key = (await _fresh(db, photo.id)).blur_key
    assert blur_key is not None and (PUBLIC, blur_key) in storage.objects
    if db.in_transaction():
        await db.commit()

    await service.delete_photo(
        db,
        user,
        photo.id,
        storage=storage,
        settings=make_test_settings(),
        queue=FakeQueue(),
    )

    assert (PUBLIC, blur_key) not in storage.objects
    assert (PUBLIC, f"p/{photo.id}.jpg") not in storage.objects
