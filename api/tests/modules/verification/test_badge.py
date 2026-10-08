"""The badge (T-4.12, D-393): each shown photo with a face compared with the
kept selfie by `verification.service.match_photo`, the result in that photo's
record and never a rejection; and `repository.shows_badge`, the query T-6.2's
`Card` carries: `is_verified` and at least one shown face that matched, never
`is_verified` alone."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core.enums import ReviewStatus
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification import repository, rules, service
from app.modules.verification.models import Verification
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import (
    PRIVATE,
    PUBLIC,
    approved_photo,
    at_selfie,
    face_photo,
    fresh,
    jpeg,
    selfie,
)

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)


async def _kept(
    db: AsyncSession, storage: FakeStorage, user: User
) -> tuple[Verification, Photo]:
    """The selfie matched the face photo: `is_verified`, the verification and
    its selfie approved, as `verify` leaves them (T-4.5)."""
    await face_photo(db, storage, user)
    shot = await selfie(db, storage, user, data=jpeg("salmon"))
    shot.status = ReviewStatus.APPROVED
    verification = Verification(
        user_id=user.id,
        challenge="none",
        selfie_photo_id=shot.id,
        status=ReviewStatus.APPROVED,
    )
    db.add(verification)
    user.is_verified = True
    await db.flush()
    return verification, shot


async def _match(
    db: AsyncSession,
    photo: Photo,
    storage: FakeStorage,
    facematch: FakeFaceMatch,
) -> str:
    return await service.match_photo(
        Sessions(db),
        photo.id,
        storage=storage,
        facematch=facematch,
        settings=make_test_settings(),
    )


def _similarity(*numbers: float | None) -> FaceMatch:
    return FaceMatch(model="fake", faces_in_selfie=1, similarities=numbers)


# --- The comparison ------------------------------------------------------------------


async def test_a_shown_face_that_matches_counts_toward_the_badge(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kept selfie's private copy against the shown photo's public copy
    (the bytes moderation scored, T-4.4), the result in the photo's record,
    exactly, with the verification it was compared for."""
    monkeypatch.setattr(core_clock, "now", lambda: NOON)
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    verification, shot = await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user, data=jpeg("navy"))
    facematch.next = _similarity(rules.MATCH_THRESHOLD)
    assert not await repository.shows_badge(db, user.id)

    assert await _match(db, photo, storage, facematch) == "matched"

    [(compared_selfie, references)] = facematch.compared
    assert compared_selfie == storage.objects[(PRIVATE, shot.raw_key)].data
    assert references == (storage.objects[(PUBLIC, f"p/{photo.id}.jpg")].data,)
    decided = await fresh(db, Photo, photo.id)
    assert decided.status is ReviewStatus.APPROVED
    assert decided.moderation["selfie_match"] == {
        "verification_id": str(verification.id),
        "provider": "fake",
        "similarity": 0.363,
        "threshold": 0.363,
        "matched": True,
        "decided_by": "queue",
        "at": NOON.isoformat(),
    }
    assert decided.moderation["faces"] == 1  # the scores stay beside it
    assert await repository.shows_badge(db, user.id)


async def test_a_shown_face_that_doesnt_match_isnt_rejected_and_doesnt_count(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-393 rule 3: her photo from behind, in sunglasses or with a friend
    stays on her profile; it just doesn't carry the badge."""
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)
    facematch.next = _similarity(0.3629)

    assert await _match(db, photo, storage, facematch) == "no_match"

    decided = await fresh(db, Photo, photo.id)
    assert (decided.status, decided.reject_reason) == (ReviewStatus.APPROVED, None)
    assert decided.moderation["selfie_match"]["matched"] is False
    assert decided.moderation["selfie_match"]["similarity"] == 0.3629
    assert (PUBLIC, f"p/{photo.id}.jpg") in storage.objects
    assert not await repository.shows_badge(db, user.id)


async def test_no_face_found_in_it_now_is_no_match(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)
    facematch.next = _similarity(None)

    assert await _match(db, photo, storage, facematch) == "no_match"

    record = (await fresh(db, Photo, photo.id)).moderation["selfie_match"]
    assert (record["similarity"], record["matched"]) == (None, False)


async def test_compared_once_for_a_verification(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)
    await _match(db, photo, storage, facematch)

    again = await _match(db, photo, storage, facematch)

    assert again == "already compared: nothing to do"
    assert len(facematch.compared) == 1


@pytest.mark.parametrize(
    "case",
    ["no selfie kept", "no face in it", "not shown", "someone refused"],
)
async def test_nothing_to_compare_leaves_the_photo_alone(
    db: AsyncSession, make_user: MakeUser, case: str
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    if case != "no selfie kept":
        await _kept(db, storage, user)
    photo = await approved_photo(
        db, storage, user, faces=0 if case == "no face in it" else 1
    )
    if case == "not shown":
        photo.status = ReviewStatus.REJECTED
        await db.flush()
    photo_id = uuid.uuid4() if case == "someone refused" else photo.id

    result = await service.match_photo(
        Sessions(db),
        photo_id,
        storage=storage,
        facematch=facematch,
        settings=make_test_settings(),
    )

    assert result in {
        "no selfie kept: nothing to compare with",
        "no face in it: nothing to compare",
        "not a shown photo: nothing to compare",
        "no such photo: its user was refused, and it went with them",
    }
    assert facematch.compared == []
    assert "selfie_match" not in ((await fresh(db, Photo, photo.id)).moderation or {})


async def test_a_file_gone_is_left_as_it_is_and_storage_down_is_tried_again(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)
    await storage.delete(PUBLIC, f"p/{photo.id}.jpg")

    assert (
        await _match(db, photo, storage, facematch) == "a file is gone: left as it is"
    )

    async def down(*args: object, **kwargs: object) -> bytes:
        raise ConnectionError("storage is down")

    monkeypatch.setattr(storage, "read_prefix", down)
    with pytest.raises(service.TryAgain) as again:
        await _match(db, photo, storage, facematch)
    assert again.value.event == "verification.storage_failed"


async def test_a_photo_removed_while_it_was_compared_is_left_as_it_is(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)
    original = facematch.compare

    async def remove_then_compare(selfie_bytes: bytes, refs: object) -> FaceMatch:
        photo.status = ReviewStatus.REJECTED
        photo.reject_reason = "user_deleted"
        await db.flush()
        return await original(selfie_bytes, refs)  # type: ignore[arg-type]

    monkeypatch.setattr(facematch, "compare", remove_then_compare)

    result = await _match(db, photo, storage, facematch)

    assert result == "no longer shown while it was compared: left as it is"
    assert "selfie_match" not in (await fresh(db, Photo, photo.id)).moderation


async def test_no_key_or_url_in_any_log(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    storage, facematch = FakeStorage(), FakeFaceMatch()
    user, _ = await at_selfie(db, make_user)
    _, shot = await _kept(db, storage, user)
    photo = await approved_photo(db, storage, user)

    await _match(db, photo, storage, facematch)

    logged = captured_logs.text
    assert "badge.compared" in logged
    for leak in (shot.raw_key, f"p/{photo.id}.jpg", "http"):
        assert leak not in logged
    captured_logs.assert_listening()


# --- The rule and the query -------------------------------------------------------------


@pytest.mark.parametrize(
    ("verified", "matched", "badge"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
    ids=["matched both ways", "selfie only", "a shown face only", "neither"],
)
def test_the_badge_needs_both(verified: bool, matched: bool, badge: bool) -> None:
    assert rules.badge(verified, matched) is badge


@pytest.mark.critical
async def test_the_query_needs_is_verified_and_a_shown_face_that_matched(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-393 rules 1 and 4: a matched selfie with no shown face, a shown face
    whose comparison said no, a match on a photo since removed, on one still
    pending, or on a private one: no badge. One approved public photo whose
    record says `matched`: the badge."""
    storage = FakeStorage()
    user, _ = await at_selfie(db, make_user)
    await _kept(db, storage, user)
    assert not await repository.shows_badge(db, user.id)

    unmatched = await approved_photo(db, storage, user, position=0)
    unmatched.moderation = {"faces": 1, "selfie_match": {"matched": False}}
    removed = await approved_photo(db, storage, user, position=1)
    removed.moderation = {"faces": 1, "selfie_match": {"matched": True}}
    removed.status = ReviewStatus.REJECTED
    removed.reject_reason = "user_deleted"
    pending = Photo(
        user_id=user.id,
        kind="public",
        position=2,
        raw_key=f"raw/{user.id}/{uuid.uuid4()}",
        moderation={"faces": 1, "selfie_match": {"matched": True}},
    )
    private = Photo(
        user_id=user.id,
        kind="private",
        raw_key=f"raw/{user.id}/{uuid.uuid4()}",
        status=ReviewStatus.APPROVED,
        moderation={"faces": 1, "selfie_match": {"matched": True}},
    )
    db.add_all([pending, private])
    await db.flush()
    assert not await repository.shows_badge(db, user.id)

    matched = await approved_photo(db, storage, user, position=3)
    matched.moderation = {"faces": 1, "selfie_match": {"matched": True}}
    await db.flush()
    assert await repository.shows_badge(db, user.id)

    # Never `is_verified` alone: the same photos, the selfie's match undone.
    user.is_verified = False
    await db.flush()
    assert not await repository.shows_badge(db, user.id)
