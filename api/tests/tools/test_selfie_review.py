"""The founder's selfie review (D-264): every decision listed, not only those
near the threshold, since the attack that matters scores far above it; each
verdict written where P-160 will read it; links for his eyes, never a log's."""

from __future__ import annotations

import io

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.modules.photos.models import Photo
from app.modules.verification import service
from app.modules.verification.models import Verification
from app.tools import selfie_review
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import (
    approved_photo,
    at_selfie,
    fresh,
    submitted,
)


async def _decided(
    db: AsyncSession,
    make_user: MakeUser,
    storage: FakeStorage,
    gender: Gender,
    *similarities: float | None,
) -> tuple[Verification, Photo, list[Photo]]:
    user, _ = await at_selfie(db, make_user, gender)
    photos = [
        await approved_photo(db, storage, user, position=n)
        for n in range(len(similarities))
    ]
    verification, selfie = await submitted(db, storage, user)
    facematch = FakeFaceMatch()
    facematch.next = FaceMatch("fake", 1, tuple(similarities))
    await service.verify(
        Sessions(db),
        verification.id,
        storage=storage,
        facematch=facematch,
        settings=make_test_settings(),
        via="queue",
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
    score: listed, with the selfie to look at, beside the near one and the one
    whose photos didn't all match."""
    storage = FakeStorage()
    far, far_selfie, _ = await _decided(db, make_user, storage, Gender.FEMALE, 0.92)
    near, _, _ = await _decided(db, make_user, storage, Gender.MALE, 0.30)
    mixed, _, photos = await _decided(db, make_user, storage, Gender.FEMALE, 0.81, 0.05)

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
    assert f"photo 1: 0.05000  /p/{photos[1].id}.jpg" in blocks[str(mixed.id)]


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
