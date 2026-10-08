"""`photos.service.moderate`, the `moderate_photo` job's work (T-4.4): each
outcome, D-093's possible minor, and what happens when the photo changes while
it is being checked. The fake moderation answers in Sightengine's documented
shape (D-094), through the same reader as the real one."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers.moderation import MINOR_MODEL, FakeModeration
from app.core.providers.storage import FakeStorage, ObjectNotFound
from app.core.queue import MATCH_PHOTO, FakeQueue
from app.modules.photos import service
from app.modules.photos.models import Photo
from app.modules.safety.models import FraudEvent
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.fixtures.located import make as located

PUBLIC, PRIVATE = "velora-public", "velora-private"
LOCATED_JPEG = (
    Path(__file__).resolve().parents[2] / "fixtures" / "located" / "located.jpg"
)


class Sessions:
    """The worker's sessionmaker, handing out the test's own session, rolled
    back with the test. A real session starts with no transaction open; one
    the test wrote through is ended first, as `session_for_the_app` does (here
    a commit only releases a savepoint)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def __call__(self) -> Sessions:
        return self

    async def __aenter__(self) -> AsyncSession:
        if self.session.in_transaction():
            await self.session.commit()
        return self.session

    async def __aexit__(self, *exc: object) -> None:
        return None


def _jpeg(size: tuple[int, int] = (800, 600), colour: str = "teal") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "JPEG")
    return out.getvalue()


async def _pending(
    db: AsyncSession,
    storage: FakeStorage,
    user: User,
    *,
    kind: PhotoKind = PhotoKind.PUBLIC,
    data: bytes | None = None,
    position: int = 0,
) -> Photo:
    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        user_id=user.id,
        kind=kind,
        position=position if kind is PhotoKind.PUBLIC else None,
        raw_key=f"raw/{user.id}/{photo_id}",
    )
    db.add(photo)
    await db.flush()
    await storage.put_bytes(PRIVATE, photo.raw_key, data or _jpeg(), "image/jpeg")
    return photo


async def _moderate(
    db: AsyncSession,
    photo: Photo,
    storage: FakeStorage,
    moderation: FakeModeration,
    queue: FakeQueue | None = None,
) -> str:
    return await service.moderate(
        Sessions(db),
        photo.id,
        storage=storage,
        moderation=moderation,
        queue=queue or FakeQueue(),
        settings=make_test_settings(),
    )


async def _fresh(db: AsyncSession, photo_id: uuid.UUID) -> Photo:
    photo = await db.scalar(
        select(Photo)
        .where(Photo.id == photo_id)
        .execution_options(populate_existing=True)
    )
    assert photo is not None
    return photo


async def _signals(db: AsyncSession, user: User) -> list[FraudEvent]:
    return list(
        await db.scalars(select(FraudEvent).where(FraudEvent.user_id == user.id))
    )


# --- Approved ------------------------------------------------------------------------


async def test_an_approved_public_photo_is_published_from_the_bytes_scored(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    upload = _jpeg((3200, 2400))
    photo = await _pending(db, storage, user, data=upload)

    assert await _moderate(db, photo, storage, moderation) == "approved"

    after = await _fresh(db, photo.id)
    assert after.status is ReviewStatus.APPROVED
    assert after.public_key == f"p/{photo.id}.jpg"
    assert (after.width, after.height) == (1600, 1200)
    [scored] = moderation.checked
    # The private copy is the re-encoded one: no original is kept.
    private = storage.objects[(PRIVATE, photo.raw_key)]
    assert private.data == scored != upload
    assert storage.objects[(PUBLIC, f"p/{photo.id}.jpg")].data == scored
    assert after.moderation == {
        "provider": "sightengine",
        "models": ["nudity-2.1", "face-age", "text"],
        "minor": 0.01,
        "explicit": 0.01,
        "faces": 1,
        "artificial_faces": 0,
        "text_artificial": 0.01,
    }


async def test_an_approved_private_photo_never_reaches_the_public_bucket(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=PhotoKind.PRIVATE)

    assert await _moderate(db, photo, storage, FakeModeration()) == "approved"

    after = await _fresh(db, photo.id)
    assert (after.status, after.public_key) == (ReviewStatus.APPROVED, None)
    assert {bucket for bucket, _ in storage.objects} == {PRIVATE}


async def test_an_approved_private_photo_is_kept_scored_where_no_upload_url_reaches(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """P-79, D-700: the bytes scored go to `scored_key` as well, a key under a
    prefix no presigned PUT is ever made for, so T-8.4's album has a copy
    nobody could have replaced after it was scored."""
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=PhotoKind.PRIVATE)

    assert await _moderate(db, photo, storage, moderation) == "approved"

    after = await _fresh(db, photo.id)
    [scored] = moderation.checked
    assert after.scored_key == f"scored/{user.id}/{photo.id}.jpg"
    assert not after.scored_key.startswith("raw/")
    assert after.scored_key != after.raw_key
    assert storage.objects[(PRIVATE, after.scored_key)].data == scored
    assert set(storage.objects) == {
        (PRIVATE, photo.raw_key),
        (PRIVATE, after.scored_key),
    }


async def test_a_private_photos_scored_copy_survives_a_second_put_before_or_after(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The hole P-79 closes: the upload URL lasts 5 minutes and outlives
    `complete`. A PUT while Sightengine is asked, and another after the
    approval, both land on the upload's key; the scored copy, and the link
    its owner is given, stay the bytes that were scored."""
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=PhotoKind.PRIVATE)

    class Swapped(FakeModeration):
        async def check(self, image: bytes) -> Any:
            await storage.put_bytes(PRIVATE, photo.raw_key, b"swapped", "image/jpeg")
            return await super().check(image)

    moderation = Swapped()
    assert await _moderate(db, photo, storage, moderation) == "approved"
    await storage.put_bytes(PRIVATE, photo.raw_key, b"after", "image/jpeg")

    after = await _fresh(db, photo.id)
    assert after.scored_key is not None
    assert storage.objects[(PRIVATE, after.scored_key)].data == moderation.checked[0]
    async with Sessions(db)() as session:
        shown = await service.owners_photo(
            session, user, photo.id, storage=storage, settings=make_test_settings()
        )
    assert (
        shown.url == f"fake-storage://{PRIVATE}/{after.scored_key}?method=GET&ttl=600"
    )


async def test_the_public_copy_is_what_was_scored_even_if_the_upload_changed(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A second PUT to the upload's URL, while Sightengine was asked, never
    reaches the public bucket: the copy published is the bytes scored."""
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    class Swapped(FakeModeration):
        async def check(self, image: bytes) -> Any:
            await storage.put_bytes(PRIVATE, photo.raw_key, b"swapped", "image/jpeg")
            return await super().check(image)

    moderation = Swapped()
    await _moderate(db, photo, storage, moderation)

    assert storage.objects[(PUBLIC, f"p/{photo.id}.jpg")].data == moderation.checked[0]


@pytest.mark.parametrize(
    ("kind", "outcome"),
    [
        (PhotoKind.PRIVATE, "nudity"),
        (PhotoKind.PUBLIC, "approved"),
        (PhotoKind.VERIFICATION, "approved"),
    ],
)
async def test_only_an_approved_private_photo_gets_a_scored_copy(
    db: AsyncSession, make_user: MakeUser, kind: PhotoKind, outcome: str
) -> None:
    """A rejected private photo is shown to nobody, a public one's shown copy
    is its public copy, and the face photo is its owner's alone (D-391)."""
    storage, moderation = FakeStorage(), FakeModeration()
    if outcome != "approved":
        moderation.next = f"reject:{outcome}"
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=kind)

    assert await _moderate(db, photo, storage, moderation) == outcome

    assert (await _fresh(db, photo.id)).scored_key is None
    assert [key for _, key in storage.objects if key.startswith("scored/")] == []


# --- Rejected --------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["nudity", "no_face", "text_overlay"])
async def test_a_rejected_photo_keeps_only_its_reencoded_copy_privately(
    db: AsyncSession, make_user: MakeUser, reason: str
) -> None:
    """`no_face` on the face photo, the one kind it still applies to (D-392)."""
    storage, moderation = FakeStorage(), FakeModeration()
    moderation.next = f"reject:{reason}"
    user, _ = await make_user()
    kind = PhotoKind.VERIFICATION if reason == "no_face" else PhotoKind.PUBLIC
    photo = await _pending(db, storage, user, kind=kind)

    assert await _moderate(db, photo, storage, moderation) == reason

    after = await _fresh(db, photo.id)
    assert (after.status, after.reject_reason) == (ReviewStatus.REJECTED, reason)
    assert (after.public_key, after.scored_key) == (None, None)
    assert list(storage.objects) == [(PRIVATE, photo.raw_key)]
    assert storage.objects[(PRIVATE, photo.raw_key)].data == moderation.checked[0]
    assert await _signals(db, user) == []


@pytest.mark.parametrize("kind", [PhotoKind.PUBLIC, PhotoKind.PRIVATE])
async def test_a_public_or_private_photo_needs_no_face(
    db: AsyncSession, make_user: MakeUser, kind: PhotoKind
) -> None:
    """D-392 (D-101 amended): hair over the face, a mask, a photo from
    behind, an emoji over it, a photo with no face at all: all approved, a
    public one published as any other."""
    storage, moderation = FakeStorage(), FakeModeration()
    moderation.next = "reject:no_face"
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=kind)

    assert await _moderate(db, photo, storage, moderation) == "approved"

    decided = await _fresh(db, photo.id)
    assert decided.moderation is not None
    assert (decided.status, decided.moderation["faces"]) == (ReviewStatus.APPROVED, 0)
    assert ((PUBLIC, f"p/{photo.id}.jpg") in storage.objects) is (
        kind is PhotoKind.PUBLIC
    )


async def test_the_face_photo_needs_a_face_and_is_never_published(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-391: the face photo exists to be compared with the selfie, so a face
    is the one thing it must show; approved, it stays in the private bucket,
    the scored bytes written back over the upload, with no public copy."""
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    faceless = await _pending(db, storage, user, kind=PhotoKind.VERIFICATION)
    moderation.next = "reject:no_face"
    assert await _moderate(db, faceless, storage, moderation) == "no_face"
    assert (await _fresh(db, faceless.id)).reject_reason == "no_face"

    face = await _pending(db, storage, user, kind=PhotoKind.VERIFICATION)
    assert await _moderate(db, face, storage, moderation) == "approved"

    decided = await _fresh(db, face.id)
    assert decided.moderation is not None
    assert (decided.status, decided.public_key, decided.moderation["faces"]) == (
        ReviewStatus.APPROVED,
        None,
        1,
    )
    assert [key for bucket, key in storage.objects if bucket == PUBLIC] == []
    assert storage.objects[(PRIVATE, face.raw_key)].data[:3] == b"\xff\xd8\xff"


@pytest.mark.parametrize(
    ("kind", "outcome", "verified", "queued"),
    [
        (PhotoKind.PUBLIC, "approve", True, True),
        (PhotoKind.PUBLIC, "reject:no_face", True, False),
        (PhotoKind.PUBLIC, "approve", False, False),
        (PhotoKind.PRIVATE, "approve", True, False),
        (PhotoKind.VERIFICATION, "approve", True, False),
    ],
    ids=[
        "a-shown-face-with-a-selfie-kept",
        "a-shown-photo-with-no-face",
        "no-selfie-kept",
        "a-private-photo",
        "the-face-photo",
    ],
)
async def test_an_approved_public_photo_with_a_face_is_queued_for_the_badge(
    db: AsyncSession,
    make_user: MakeUser,
    kind: PhotoKind,
    outcome: str,
    verified: bool,
    queued: bool,
) -> None:
    """D-393: approved, with a face, and a selfie already kept (`is_verified`,
    T-4.5's own word): compared with that selfie on the worker, under its own
    job id. Nothing else is."""
    storage, moderation, queue = FakeStorage(), FakeModeration(), FakeQueue()
    user, _ = await make_user(verified=verified)
    photo = await _pending(db, storage, user, kind=kind)
    moderation.next = outcome

    await _moderate(db, photo, storage, moderation, queue)

    assert [(job.job_id, job.kwargs) for job in queue.named(MATCH_PHOTO)] == (
        [(f"match_photo:{photo.id}", {"photo_id": str(photo.id)})] if queued else []
    )


async def test_a_shown_copy_keeps_which_face_photo_it_came_from(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """`show_face_photo` makes a pending public copy carrying `from_photo_id`
    (T-4.12); the decision writes the scores beside it, never over it."""
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    source = uuid.uuid4()
    photo = await _pending(db, storage, user)
    photo.moderation = {"from_photo_id": str(source)}
    await db.flush()

    assert await _moderate(db, photo, storage, moderation) == "approved"

    record = (await _fresh(db, photo.id)).moderation
    assert record is not None
    assert record["from_photo_id"] == str(source)
    assert record["provider"] == "sightengine"


# --- A possible minor (D-093) ----------------------------------------------------------


async def test_a_possible_minor_is_rejected_recorded_as_a_score_and_every_copy_deleted(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    moderation.next = "reject:minor_suspected"
    user, _ = await make_user(gender="female")
    photo = await _pending(db, storage, user)
    # A public copy at its key, as if one had ever been written: it goes too.
    await storage.put_bytes(PUBLIC, f"p/{photo.id}.jpg", b"old", "image/jpeg")

    assert await _moderate(db, photo, storage, moderation) == "minor_suspected"

    after = await _fresh(db, photo.id)
    assert (after.status, after.reject_reason) == (
        ReviewStatus.REJECTED,
        "minor_suspected",
    )
    assert storage.objects == {}
    [signal] = await _signals(db, user)
    assert (signal.signal, signal.weight) == ("possible_minor_photo_score", 0)
    # The minimal record: the user and when (the row), the score and the model.
    assert signal.meta == {
        "what": "A model's score for one photo, not a finding about the person "
        "(D-093).",
        "model": MINOR_MODEL,
        "score": 0.93,
    }
    assert str(photo.id) not in str(signal.meta)


async def test_a_minor_score_wins_over_nudity(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A photo scoring both is handled as D-093 says: deleted, never kept as
    an ordinary nudity rejection."""
    storage = FakeStorage()

    class Both(FakeModeration):
        async def check(self, image: bytes) -> Any:
            scores = await super().check(image)
            return type(scores)(
                **{
                    **scores.__dict__,
                    "minors": (0.93,),
                    "nudity": {**scores.nudity, "erotica": 0.99},
                }
            )

    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    assert await _moderate(db, photo, storage, Both()) == "minor_suspected"
    assert storage.objects == {}


class _DeleteThatDoesntDelete(FakeStorage):
    async def delete(self, bucket: str, key: str) -> None:
        return None


async def test_a_possible_minors_photo_still_stored_is_tried_again_until_gone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-090's rule for D-093's deletion: success from a delete isn't proof.
    The read-back finds it; the job's next try deletes again."""
    storage, moderation = _DeleteThatDoesntDelete(), FakeModeration()
    moderation.next = "reject:minor_suspected"
    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    with pytest.raises(service.TryAgain) as again:
        await _moderate(db, photo, storage, moderation)
    assert again.value.event == "moderation.minor_photo_not_deleted"
    assert (await _fresh(db, photo.id)).reject_reason == "minor_suspected"

    working = FakeStorage()
    working.objects = storage.objects
    result = await _moderate(db, photo, working, moderation)

    assert result == "a possible minor's photo: every copy gone"
    assert working.objects == {}
    assert len(await _signals(db, user)) == 1  # recorded once


# --- What the worker can't read --------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"<!doctype html><script>alert(1)</script>", "other"),
        (b"\xff\xd8\xff" + b"\x00" * 200, "other"),
        (b"\xff\xd8\xff" + b"\x00" * (8 * 1024 * 1024), "too_large"),
    ],
    ids=["not an image", "a JPEG in name only", "over 8 MB since complete"],
)
async def test_what_the_worker_cant_read_is_rejected_and_its_file_removed(
    db: AsyncSession, make_user: MakeUser, data: bytes, reason: str
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, data=data)

    assert await _moderate(db, photo, storage, moderation) == reason

    after = await _fresh(db, photo.id)
    assert (after.status, after.reject_reason) == (ReviewStatus.REJECTED, reason)
    assert storage.objects == {}
    assert moderation.checked == []


async def test_the_bytes_decide_again_not_what_complete_saw(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Replaced by a PNG after `complete` judged a JPEG: read as the PNG."""
    out = io.BytesIO()
    Image.new("RGB", (300, 200), "orange").save(out, "PNG")
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, data=out.getvalue())

    assert await _moderate(db, photo, storage, FakeModeration()) == "approved"


# --- Once, and only while it waits -----------------------------------------------------


async def test_running_it_again_on_a_decided_photo_does_nothing(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    photo = await _pending(db, storage, user)
    await _moderate(db, photo, storage, moderation)
    before = dict(storage.objects)

    assert (
        await _moderate(db, photo, storage, moderation)
        == "already approved: nothing to do"
    )

    assert len(moderation.checked) == 1
    assert storage.objects == before


async def test_a_selfie_is_left_to_verification(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=PhotoKind.SELFIE)

    assert "T-4.5" in await _moderate(db, photo, storage, moderation)
    assert (await _fresh(db, photo.id)).status is ReviewStatus.PENDING
    assert moderation.checked == []


async def test_a_photo_its_owner_removed_while_it_was_checked_is_never_published(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.PHOTOS  # where one photo may go
    photo = await _pending(db, storage, user)

    class OwnerRemovesIt(FakeModeration):
        async def check(self, image: bytes) -> Any:
            await service.delete_photo(
                db,
                user,
                photo.id,
                storage=storage,
                settings=make_test_settings(),
            )
            return await super().check(image)

    result = await _moderate(db, photo, storage, OwnerRemovesIt())

    assert result == "rejected while it was checked: left as it is"
    after = await _fresh(db, photo.id)
    assert (after.status, after.reject_reason) == (
        ReviewStatus.REJECTED,
        "user_deleted",
    )
    assert (PUBLIC, f"p/{photo.id}.jpg") not in storage.objects


async def test_a_user_refused_while_their_photo_was_checked_leaves_no_file(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal deletes the rows (D-078) and queues the files' deletion,
    which may already have run when the re-encoded copy was written: the job
    removes what it wrote. The refusal itself is stood in for: the user's row
    reads as gone."""
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    async def gone(session: AsyncSession, user_id: uuid.UUID) -> User:
        raise LookupError("no such user")

    monkeypatch.setattr(users_service, "locked_user", gone)
    result = await _moderate(db, photo, storage, FakeModeration())

    assert result == "its user was refused while it was checked: its file removed"
    assert storage.objects == {}


# --- Failures: tried again by the job ----------------------------------------------------


async def test_a_moderation_failure_tries_again_and_keeps_no_original(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    moderation.next = "fail"
    user, _ = await make_user()
    upload = LOCATED_JPEG.read_bytes()
    photo = await _pending(db, storage, user, data=upload)

    with pytest.raises(service.TryAgain) as again:
        await _moderate(db, photo, storage, moderation)

    assert again.value.event == "moderation.failed_photo"
    assert (await _fresh(db, photo.id)).status is ReviewStatus.PENDING
    # Re-encoded before Sightengine was asked: the located original is gone.
    kept = storage.objects[(PRIVATE, photo.raw_key)].data
    assert located.COORDINATES.encode() not in kept
    assert b"Exif" not in kept


class _Unreachable(FakeStorage):
    async def read_prefix(self, bucket: str, key: str, length: int) -> bytes:
        raise ConnectionError("R2 is down")


async def test_storage_failing_tries_again(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = _Unreachable()
    user, _ = await make_user()
    photo = await _pending(db, storage, user)

    with pytest.raises(service.TryAgain) as again:
        await _moderate(db, photo, storage, FakeModeration())
    assert (again.value.event, str(again.value)) == (
        "moderation.storage_failed",
        "ConnectionError",
    )


async def test_a_photo_whose_file_is_gone_is_left_alone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await make_user()
    photo = await _pending(db, storage, user)
    await storage.delete(PRIVATE, photo.raw_key)

    assert (
        await _moderate(db, photo, storage, FakeModeration()) == "no file to moderate"
    )
    with pytest.raises(ObjectNotFound):
        await storage.head(PRIVATE, photo.raw_key)


# --- Critical #14, through the whole pipeline ------------------------------------------


@pytest.mark.critical
@pytest.mark.parametrize("kind", [PhotoKind.PUBLIC, PhotoKind.PRIVATE])
async def test_a_located_photo_is_stored_with_no_location_anywhere(
    db: AsyncSession, make_user: MakeUser, kind: PhotoKind
) -> None:
    """Critical #14: a photo carrying GPS goes in; every copy stored, and the
    bytes sent to Sightengine, carry none of it."""
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    photo = await _pending(db, storage, user, kind=kind, data=LOCATED_JPEG.read_bytes())

    assert await _moderate(db, photo, storage, moderation) == "approved"

    copies = [stored.data for stored in storage.objects.values()] + moderation.checked
    # The upload re-encoded, the bytes scored, and the shown copy: a public
    # photo's public copy, a private one's scored copy (P-79, D-700).
    assert len(copies) == 3
    for data in copies:
        header = data[: data.index(b"\xff\xda")]
        for mark in (b"Exif", b"GPS", b"xmp", b"ICC_PROFILE", located.MAKE.encode()):
            assert mark not in header
        assert located.COORDINATES.encode() not in data
        assert located.TRAILER_MARK.encode() not in data


# --- Rule 15 -----------------------------------------------------------------------------


async def test_no_key_url_or_image_bytes_in_any_log(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    storage, moderation = FakeStorage(), FakeModeration()
    user, _ = await make_user()
    photos = [await _pending(db, storage, user, position=n) for n in range(3)]
    moderation.next = "reject:minor_suspected"
    await _moderate(db, photos[0], storage, moderation)
    await _moderate(db, photos[1], storage, moderation)
    moderation.next = "fail"
    with pytest.raises(service.TryAgain):
        await _moderate(db, photos[2], storage, moderation)

    logged = captured_logs.text
    assert "moderation.decided" in logged
    for photo in photos:
        assert photo.raw_key not in logged
        assert f"p/{photo.id}.jpg" not in logged
    assert "raw/" not in logged
    assert "fake-storage://" not in logged
    assert "JFIF" not in logged
    captured_logs.assert_listening()
