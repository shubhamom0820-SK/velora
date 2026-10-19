"""The founder's selfie review (D-264): every decision listed, not only those
near the threshold, since the attack that matters scores far above it; each
verdict written where P-160 will read it; links for his eyes, never a log's."""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, OnboardingStep, Role
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.core.queue import FakeQueue
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification import service
from app.modules.verification.models import Verification
from app.tools import selfie_review
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import (
    approved_photo,
    at_selfie,
    face_photo,
    fresh,
    submitted,
)


async def _decided(
    db: AsyncSession,
    make_user: MakeUser,
    storage: FakeStorage,
    gender: Gender,
    similarity: float | None,
    *shown: float | None,
) -> tuple[Verification, Photo, list[Photo]]:
    """A selfie compared with the face photo at `similarity` (D-391), then each
    shown photo compared with it at its own number for the badge (D-393), as
    the worker would run them."""
    user, _ = await at_selfie(db, make_user, gender)
    await face_photo(db, storage, user)
    photos = [
        await approved_photo(db, storage, user, position=n) for n in range(len(shown))
    ]
    verification, selfie = await submitted(db, storage, user)
    facematch = FakeFaceMatch()
    facematch.next = FaceMatch("fake", 1, (similarity,))
    await service.verify(
        Sessions(db),
        verification.id,
        storage=storage,
        facematch=facematch,
        queue=FakeQueue(),
        settings=make_test_settings(),
        via="queue",
    )
    for photo, number in zip(photos, shown, strict=True):
        facematch.next = FaceMatch("fake", 1, (number,))
        await service.match_photo(
            Sessions(db),
            photo.id,
            storage=storage,
            facematch=facematch,
            settings=make_test_settings(),
        )
    return verification, selfie, photos


async def _review(
    db: AsyncSession, storage: FakeStorage, *argv: str
) -> tuple[int, str]:
    out = io.StringIO()
    code = await selfie_review.run(
        selfie_review.parse(argv),
        sessions=Sessions(db),
        storage=storage,
        settings=make_test_settings(),
        out=out,
    )
    return code, out.getvalue()


async def test_every_decision_is_listed_far_from_the_threshold_too(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A woman approved at 0.92 is exactly what her own stolen selfie would
    score: listed, with the selfie and the face photo to look at, beside the
    near one and the one whose shown photos didn't all match."""
    storage = FakeStorage()
    far, far_selfie, _ = await _decided(db, make_user, storage, Gender.FEMALE, 0.92)
    near, _, _ = await _decided(db, make_user, storage, Gender.MALE, 0.30)
    mixed, _, photos = await _decided(
        db, make_user, storage, Gender.FEMALE, 0.81, 0.77, 0.05
    )

    code, printed = await _review(db, storage)

    assert code == 0
    assert "3 to look at" in printed
    blocks = {b.split()[0]: b for b in printed.split("\n\n")[1:]}
    assert set(blocks) == {str(far.id), str(near.id), str(mixed.id)}
    assert "female  approved  best 0.92000\n" in blocks[str(far.id)]
    assert "NEAR" in blocks[str(near.id)] and "no_match" in blocks[str(near.id)]
    assert "MIXED" in blocks[str(mixed.id)]
    assert (
        f"selfie:  fake-storage://velora-private/{far_selfie.raw_key}"
        "?method=GET&ttl=600" in blocks[str(far.id)]
    )
    assert "face photo: 0.92000  fake-storage://velora-private/" in blocks[str(far.id)]
    assert f"shown 0: 0.77000  /p/{photos[0].id}.jpg" in blocks[str(mixed.id)]
    assert f"shown 1: 0.05000  /p/{photos[1].id}.jpg" in blocks[str(mixed.id)]


async def test_near_narrows_it_to_the_near_and_the_mixed(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    far, _, _ = await _decided(db, make_user, storage, Gender.FEMALE, 0.92)
    near, _, _ = await _decided(db, make_user, storage, Gender.MALE, 0.40)

    _, printed = await _review(db, storage, "--near")

    assert str(near.id) in printed and str(far.id) not in printed


async def test_a_verdict_is_written_into_the_selfies_record_and_leaves_the_rest(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    verification, selfie, _ = await _decided(
        db, make_user, storage, Gender.FEMALE, 0.92
    )
    verification_id = verification.id

    code, printed = await _review(
        db, storage, "--verdict", str(verification_id), "different"
    )

    assert code == 0
    assert f"{verification_id} recorded as different" in printed
    record = (await fresh(db, Photo, selfie.id)).moderation
    assert record["review"]["verdict"] == "different"
    assert record["best"] == 0.92  # the decision's own numbers stay
    assert (await fresh(db, Verification, verification_id)).status.value == "approved"
    # Reviewed: listed no more, unless asked.
    assert str(verification_id) not in (await _review(db, storage))[1]
    _, everything = await _review(db, storage, "--include-reviewed")
    assert "verdict: different" in everything


@pytest.mark.parametrize(
    ("argv", "code", "says"),
    [
        (["--verdict", "not-an-id", "same"], 2, "isn't a verification id"),
        (
            ["--verdict", "00000000-0000-0000-0000-000000000000", "maybe"],
            2,
            "`same` or",
        ),
        (
            ["--verdict", "00000000-0000-0000-0000-000000000000", "same"],
            1,
            "no verification",
        ),
    ],
)
async def test_a_verdict_it_cant_record_says_why(
    db: AsyncSession, argv: list[str], code: int, says: str
) -> None:
    got, printed = await _review(db, FakeStorage(), *argv)

    assert (got, says in printed) == (code, True)


async def test_the_seeds_rows_arent_decisions(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    _, selfie, _ = await _decided(db, make_user, storage, Gender.FEMALE, 0.92)
    selfie.moderation = {"decided_by": "seed"}
    await db.flush()

    assert "0 to look at" in (await _review(db, storage))[1]


async def test_no_link_or_key_reaches_a_log(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    storage = FakeStorage()
    verification, selfie, _ = await _decided(
        db, make_user, storage, Gender.FEMALE, 0.92
    )
    await _review(db, storage)
    await _review(db, storage, "--verdict", str(verification.id), "same")

    assert "verification.reviewed" in captured_logs.text
    for leak in (selfie.raw_key, "fake-storage://", "/p/"):
        assert leak not in captured_logs.text
    captured_logs.assert_listening()


# --- The undo (P-163, D-993, D-1051) ----------------------------------------------------

UNDO_REASON = "Review: the selfie isn't the face photo's person."


async def _admin_id(make_user: MakeUser) -> str:
    admin, _ = await make_user(Gender.FEMALE)
    admin.role = Role.ADMIN
    return str(admin.id)


async def test_an_undo_sends_her_back_and_says_so(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    by = await _admin_id(make_user)
    verification, selfie, _ = await _decided(
        db, make_user, storage, Gender.FEMALE, 0.92
    )
    user = await fresh(db, User, verification.user_id)
    user.onboarding_step = OnboardingStep.DONE
    await db.flush()

    code, printed = await _review(
        db,
        storage,
        "--undo",
        str(verification.id),
        "--by",
        by,
        "--reason",
        UNDO_REASON,
    )

    assert code == 0, printed
    assert printed == (
        f"selfie_review: {verification.id} undone: the badge is gone, and "
        f"{verification.user_id} is back at the selfie step, signed in, to take it "
        f"again. Recorded in audit_log as {by}.\n"
    )
    assert (await fresh(db, Photo, selfie.id)).reject_reason == "undone"


async def test_an_undo_for_a_man_says_he_stays(
    db: AsyncSession, make_user: MakeUser
) -> None:
    storage = FakeStorage()
    by = await _admin_id(make_user)
    verification, _, _ = await _decided(db, make_user, storage, Gender.MALE, 0.92)
    user = await fresh(db, User, verification.user_id)
    user.onboarding_step = OnboardingStep.DONE
    await db.flush()

    code, printed = await _review(
        db, storage, "--undo", str(verification.id), "--by", by, "--reason", "why"
    )

    assert code == 0, printed
    assert f"{verification.user_id} stays at done" in printed


@pytest.mark.parametrize(
    ("case", "code", "says"),
    [
        ("bad-id", 2, "--undo and --by are both ids"),
        ("no-by", 2, "--undo and --by are both ids"),
        ("blank-reason", 2, "--reason can't be empty"),
        ("not-admin", 1, "isn't an active admin. Nothing changed."),
        ("nobody", 1, "no verification"),
        ("rejected", 1, "is rejected: only an approved match is undone"),
        ("same", 1, "Record it as different first"),
    ],
)
async def test_an_undo_it_wont_do_says_why_and_changes_nothing(
    db: AsyncSession, make_user: MakeUser, case: str, code: int, says: str
) -> None:
    storage = FakeStorage()
    by = await _admin_id(make_user)
    similarity = 0.1 if case == "rejected" else 0.92
    verification, _, _ = await _decided(
        db, make_user, storage, Gender.FEMALE, similarity
    )
    verification_id = str(verification.id)
    if case == "same":
        await _review(db, storage, "--verdict", verification_id, "same")
    if case == "not-admin":
        nobody, _ = await make_user(Gender.FEMALE)
        by = str(nobody.id)
    argv = {
        "bad-id": ["--undo", "nope", "--by", by, "--reason", UNDO_REASON],
        "no-by": ["--undo", verification_id, "--reason", UNDO_REASON],
        "blank-reason": ["--undo", verification_id, "--by", by, "--reason", " "],
        "nobody": ["--undo", str(uuid.uuid4()), "--by", by, "--reason", UNDO_REASON],
    }.get(case, ["--undo", verification_id, "--by", by, "--reason", UNDO_REASON])
    before = (await fresh(db, Verification, uuid.UUID(verification_id))).status

    got, printed = await _review(db, storage, *argv)

    assert (got, says in printed) == (code, True), printed
    assert (await fresh(db, Verification, uuid.UUID(verification_id))).status is before
