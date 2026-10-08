"""`verification.service.verify`, the comparison the `verify_selfie` job and a
wake run (T-4.5): each outcome, the threshold's edge, what is compared with
what (the face photo alone, D-391, T-4.12), what is recorded, and what happens
when things change meanwhile. The fake face match answers with the numbers a
test gives it; the real one is `tests/core/test_facematch.py`'s."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PhotoKind, ReviewStatus
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.core.queue import MATCH_PHOTO, FakeQueue
from app.modules.photos.models import Photo
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.verification import rules, service
from app.modules.verification.models import Verification
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.fixtures.located import make as located
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import (
    PRIVATE,
    PUBLIC,
    approved_photo,
    at_selfie,
    bearer,
    face_photo,
    fresh,
    jpeg,
    latest,
    submitted,
)

LOCATED_JPEG = (
    Path(__file__).resolve().parents[2] / "fixtures" / "located" / "located.jpg"
)


def _match(*similarities: float | None, faces: int = 1) -> FaceMatch:
    return FaceMatch(model="fake", faces_in_selfie=faces, similarities=similarities)


async def _verify(
    db: AsyncSession,
    verification: Verification,
    storage: FakeStorage,
    facematch: FakeFaceMatch,
    via: str = "queue",
    queue: FakeQueue | None = None,
) -> str:
    return await service.verify(
        Sessions(db),
        verification.id,
        storage=storage,
        facematch=facematch,
        queue=queue or FakeQueue(),
        settings=make_test_settings(),
        via=via,
    )


async def _state(
    db: AsyncSession, user: User, verification: Verification, selfie: Photo
) -> tuple[ReviewStatus, ReviewStatus, str | None, bool]:
    v = await fresh(db, Verification, verification.id)
    s = await fresh(db, Photo, selfie.id)
    u = await fresh(db, User, user.id)
    return v.status, s.status, s.reject_reason, u.is_verified


# --- Approved and rejected, at the threshold's edge (D-260) ------------------------


async def test_at_the_threshold_it_matches_and_records_the_numbers(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    face = await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)
    facematch.next = _match(rules.MATCH_THRESHOLD)

    assert await _verify(db, verification, storage, facematch, via="wake") == "approved"

    assert await _state(db, user, verification, selfie) == (
        ReviewStatus.APPROVED,
        ReviewStatus.APPROVED,
        None,
        True,
    )
    record = (await fresh(db, Photo, selfie.id)).moderation
    assert record == {
        "threshold": 0.363,
        "decided_by": "wake",
        "provider": "fake",
        "faces": 1,
        "best": 0.363,
        "compared": [{"photo_id": str(face.id), "similarity": 0.363}],
    }
    # Nothing in the column that can't hold it (numeric(5,2), D-263).
    assert (await fresh(db, Verification, verification.id)).similarity is None


def test_the_threshold_is_sface_s_published_lfw_number() -> None:
    """D-260 (Locked): OpenCV's published 0.363 for SFace on LFW, not ours.
    Changing it is changing that decision, so this fails first."""
    assert rules.MATCH_THRESHOLD == 0.363


async def test_just_below_the_threshold_it_doesnt(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)
    facematch.next = _match(0.3629)

    assert await _verify(db, verification, storage, facematch) == "no_match"

    assert await _state(db, user, verification, selfie) == (
        ReviewStatus.REJECTED,
        ReviewStatus.REJECTED,
        "no_match",
        False,
    )


async def test_the_selfie_is_compared_with_the_face_photo_alone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-391: three approved public photos with faces, and none of them is what
    the selfie is compared with. The one reference is the face photo's private
    copy; the record names it alone. (The public photos' own comparison with
    the selfie is the badge's, D-393, and queued once this match is written.)"""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    queue = FakeQueue()
    user, _ = await at_selfie(db, make_user)
    shown = [
        await approved_photo(db, storage, user, position=n, data=jpeg("navy"))
        for n in range(3)
    ]
    face = await face_photo(db, storage, user, data=jpeg("olive"))
    verification, selfie = await submitted(db, storage, user)
    facematch.next = _match(0.71)

    assert await _verify(db, verification, storage, facematch, queue=queue) == (
        "approved"
    )

    [(_, references)] = facematch.compared
    assert references == (storage.objects[(PRIVATE, face.raw_key)].data,)
    for photo in shown:
        assert storage.objects[(PUBLIC, f"p/{photo.id}.jpg")].data not in references
    compared = (await fresh(db, Photo, selfie.id)).moderation["compared"]
    assert [c["photo_id"] for c in compared] == [str(face.id)]
    assert [job.kwargs["photo_id"] for job in queue.named(MATCH_PHOTO)] == [
        str(photo.id) for photo in shown
    ]


async def test_a_match_queues_the_badges_comparison_for_each_shown_face(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-393, when the selfie is decided: every approved public photo whose
    record found a face is queued, once each under its own id; one with no
    face, a pending one and a private one aren't. A rejection queues nothing."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    queue = FakeQueue()
    user, _ = await at_selfie(db, make_user)
    with_face = await approved_photo(db, storage, user, position=0)
    await approved_photo(db, storage, user, position=1, faces=0)
    db.add(
        Photo(
            user_id=user.id,
            kind=PhotoKind.PUBLIC,
            position=2,
            raw_key=f"raw/{user.id}/{uuid.uuid4()}",
            moderation={"faces": 1},
        )
    )
    db.add(
        Photo(
            user_id=user.id,
            kind=PhotoKind.PRIVATE,
            raw_key=f"raw/{user.id}/{uuid.uuid4()}",
            status=ReviewStatus.APPROVED,
            moderation={"faces": 1},
        )
    )
    await db.flush()
    await face_photo(db, storage, user)
    verification, _ = await submitted(db, storage, user)
    facematch.next = _match(0.2)

    assert await _verify(db, verification, storage, facematch, queue=queue) == (
        "no_match"
    )
    assert queue.jobs == []

    facematch.next = _match(0.9)
    verification, _ = await submitted(db, storage, user)
    assert await _verify(db, verification, storage, facematch, queue=queue) == (
        "approved"
    )
    [job] = queue.named(MATCH_PHOTO)
    assert (job.job_id, job.kwargs) == (
        f"match_photo:{with_face.id}",
        {"photo_id": str(with_face.id)},
    )


@pytest.mark.parametrize(
    ("faces", "reason"), [(0, "no_face"), (2, "many_faces"), (3, "many_faces")]
)
async def test_the_selfie_must_hold_exactly_one_face(
    db: AsyncSession, make_user: MakeUser, faces: int, reason: str
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)
    # Many faces, one of them a perfect match: still refused.
    facematch.next = _match(None if faces == 0 else 0.99, faces=faces)

    assert await _verify(db, verification, storage, facematch) == reason

    assert (await _state(db, user, verification, selfie))[2:] == (reason, False)


async def test_a_face_photo_with_no_face_found_is_no_photos(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Moderation refuses a face photo with no face (D-101 amended); if the
    face matcher still finds none, the selfie has nothing to be compared
    with, and says so by the same name."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, _ = await submitted(db, storage, user)
    facematch.next = _match(None)

    assert await _verify(db, verification, storage, facematch) == "no_photos"


# --- What it is compared with ------------------------------------------------------


async def test_it_compares_the_re_encoded_selfie_with_the_approved_face_photo_only(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The reference is the approved face photo's private copy, the bytes
    moderation scored and wrote back over the upload (T-4.4, D-092). A face
    photo still pending or rejected, a public photo and a private one aren't
    compared at all."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    face = await face_photo(db, storage, user, data=jpeg("olive"))
    await face_photo(db, storage, user, status=ReviewStatus.REJECTED, data=jpeg("red"))
    await approved_photo(db, storage, user, data=jpeg("navy"))
    other = Photo(
        user_id=user.id,
        kind=PhotoKind.PRIVATE,
        raw_key=f"raw/{user.id}/{uuid.uuid4()}",
        status=ReviewStatus.APPROVED,
    )
    db.add(other)
    await db.flush()
    await storage.put_bytes(PRIVATE, other.raw_key, jpeg("teal"), "image/jpeg")
    verification, selfie = await submitted(db, storage, user)

    await _verify(db, verification, storage, facematch)

    [(compared_selfie, references)] = facematch.compared
    assert references == (storage.objects[(PRIVATE, face.raw_key)].data,)
    assert compared_selfie == storage.objects[(PRIVATE, selfie.raw_key)].data
    assert compared_selfie[:3] == b"\xff\xd8\xff"  # the re-encoded JPEG, written back


async def test_with_no_face_photo_there_is_nothing_to_compare_with(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Approved public photos with faces don't stand in for it (D-391)."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await approved_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)

    assert await _verify(db, verification, storage, facematch) == "no_photos"

    assert facematch.compared == []
    assert (await _state(db, user, verification, selfie))[2] == "no_photos"


async def test_while_the_face_photo_is_still_being_moderated_it_waits(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user, status=ReviewStatus.PENDING)
    verification, _ = await submitted(db, storage, user)

    with pytest.raises(service.TryAgain) as waiting:
        await _verify(db, verification, storage, facematch)

    assert (waiting.value.final, waiting.value.defer.total_seconds()) == (
        "no_photos",
        20,
    )
    assert (await fresh(db, Verification, verification.id)).status is (
        ReviewStatus.PENDING
    )


async def test_a_face_photo_whose_file_is_gone_is_no_photos(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    gone = await face_photo(db, storage, user)
    await storage.delete(PRIVATE, gone.raw_key)
    verification, selfie = await submitted(db, storage, user)

    assert await _verify(db, verification, storage, facematch) == "no_photos"

    assert facematch.compared == []
    assert "compared" not in (await fresh(db, Photo, selfie.id)).moderation


# --- The selfie itself ------------------------------------------------------------------


@pytest.mark.critical
async def test_a_located_selfie_is_stored_with_no_location(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Critical #14: a selfie carrying GPS goes in; the copy kept, and the
    bytes compared, carry none of it."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(
        db, storage, user, data=LOCATED_JPEG.read_bytes()
    )

    assert await _verify(db, verification, storage, facematch) == "approved"

    [(compared, _)] = facematch.compared
    for data in (storage.objects[(PRIVATE, selfie.raw_key)].data, compared):
        header = data[: data.index(b"\xff\xda")]
        for mark in (b"Exif", b"GPS", b"xmp", b"ICC_PROFILE", located.MAKE.encode()):
            assert mark not in header
        assert located.COORDINATES.encode() not in data
        assert located.TRAILER_MARK.encode() not in data


@pytest.mark.parametrize(
    "data",
    [b"not an image at all", b"\xff\xd8\xff" + b"\x00" * 64],
    ids=["text", "a-broken-jpeg"],
)
async def test_a_selfie_that_isnt_an_image_is_unreadable_and_its_file_goes(
    db: AsyncSession, make_user: MakeUser, data: bytes
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user, data=data)

    assert await _verify(db, verification, storage, facematch) == "unreadable"

    assert (PRIVATE, selfie.raw_key) not in storage.objects
    assert facematch.compared == []


async def test_a_selfie_whose_file_is_gone_is_unreadable(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)
    await storage.delete(PRIVATE, selfie.raw_key)

    assert await _verify(db, verification, storage, facematch) == "unreadable"


@pytest.mark.critical
async def test_a_matched_selfie_is_never_public_and_never_shown(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, fake_providers: Any
) -> None:
    """Critical #14: approved, the selfie gets no public copy and no public
    key, and neither does the face photo it matched; the selfie isn't among
    its owner's photos, can't be read as one, and the verification's answer
    carries no link, key or number."""
    storage = fake_providers.storage
    user, token = await at_selfie(db, make_user)
    photo = await approved_photo(db, storage, user)
    face = await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)
    selfie_id, raw_key = selfie.id, selfie.raw_key

    assert await _verify(db, verification, storage, FakeFaceMatch()) == "approved"

    assert (await fresh(db, Photo, selfie_id)).public_key is None
    assert (await fresh(db, Photo, face.id)).public_key is None
    assert [key for bucket, key in storage.objects if bucket == PUBLIC] == [
        f"p/{photo.id}.jpg"
    ]
    mine = await client.get("/v1/me/photos", headers=bearer(token))
    assert str(selfie_id) not in mine.text
    one = await client.get(f"/v1/photos/{selfie_id}", headers=bearer(token))
    assert one.status_code == 404
    answer = await latest(client, token)
    assert set(answer.json()) == {
        "id",
        "status",
        "submitted",
        "reject_reason",
        "attempts_left",
    }
    for leak in (str(selfie_id), raw_key, "http", "0.9"):
        assert leak not in answer.text


# --- Once, whatever runs it --------------------------------------------------------------


async def test_a_decided_one_is_left_as_it_is(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, _ = await submitted(db, storage, user)
    await _verify(db, verification, storage, facematch)

    again = await _verify(db, verification, storage, facematch)

    assert again == "already approved: nothing to do"
    assert len(facematch.compared) == 1


async def test_one_not_yet_submitted_waits_for_its_submit(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Queued before its submit committed: tried again shortly, and if the
    submit never commits, left alone (nothing to reject)."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    verification = Verification(user_id=user.id, challenge="none")
    db.add(verification)
    await db.flush()

    with pytest.raises(service.TryAgain) as waiting:
        await _verify(db, verification, storage, facematch)

    assert (waiting.value.final, waiting.value.defer.total_seconds()) == (None, 5)


async def test_a_user_refused_while_it_was_compared_leaves_no_selfie(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal deletes the rows (D-078) and queues the files' deletion,
    which may already have run when the re-encoded selfie was written back:
    the run removes what it wrote. The refusal is stood in for: the user's row
    reads as gone."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    face = await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)

    async def gone(session: AsyncSession, user_id: uuid.UUID) -> User:
        raise LookupError("no such user")

    monkeypatch.setattr(users_service, "locked_user", gone)
    result = await _verify(db, verification, storage, facematch)

    assert result == "its user was refused while it was compared: its selfie removed"
    assert (PRIVATE, selfie.raw_key) not in storage.objects
    assert (PRIVATE, face.raw_key) in storage.objects  # D-078's deletion takes it


async def test_storage_down_is_tried_again(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await face_photo(db, storage, user)
    verification, _ = await submitted(db, storage, user)

    async def down(*args: object, **kwargs: object) -> bytes:
        raise ConnectionError("storage is down")

    monkeypatch.setattr(storage, "read_prefix", down)

    with pytest.raises(service.TryAgain) as again:
        await _verify(db, verification, storage, facematch)

    assert (again.value.event, again.value.final) == (
        "verification.storage_failed",
        "unavailable",
    )


async def test_giving_up_rejects_so_the_person_can_start_again(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    user, _ = await at_selfie(db, make_user)
    verification, selfie = await submitted(db, storage, user)

    result = await service.give_up(
        Sessions(db),
        verification.id,
        rules.UNAVAILABLE,
        storage=storage,
        settings=make_test_settings(),
        via="queue",
    )

    assert result == "unavailable"
    assert await _state(db, user, verification, selfie) == (
        ReviewStatus.REJECTED,
        ReviewStatus.REJECTED,
        "unavailable",
        False,
    )


# --- Rule 15 ---------------------------------------------------------------------------


async def test_no_key_or_url_in_any_log(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    photo = await approved_photo(db, storage, user)
    face = await face_photo(db, storage, user)
    verification, selfie = await submitted(db, storage, user)

    await _verify(db, verification, storage, facematch)

    logged = captured_logs.text
    assert "verification.decided" in logged
    for leak in (selfie.raw_key, face.raw_key, f"p/{photo.id}.jpg", "http"):
        assert leak not in logged
    captured_logs.assert_listening()
