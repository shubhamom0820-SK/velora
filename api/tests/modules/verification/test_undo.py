"""Undoing a selfie match the founder's review found wrong (P-163, D-993,
D-995, D-1051): the verification and its selfie rejected, `is_verified`
cleared, every `selfie_match` it gave removed, so no badge outlives it; a
woman back at the `selfie` step, still signed in, her sockets closed; a man
left at `done`; her Threads as they were. One `audit_log` row as an active
admin; the verdict recorded `different` where none was, and a recorded
`same` refused."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, OnboardingStep, ReviewStatus, Role, UserStatus
from app.core.providers.facematch import FaceMatch, FakeFaceMatch
from app.core.providers.storage import FakeStorage
from app.modules.admin.models import AuditLogEntry
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification import repository, rules, service
from app.modules.verification.models import Verification
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.photos.test_moderate import Sessions
from tests.modules.verification.support import (
    approved_photo,
    bearer,
    error,
    face_photo,
    fresh,
    jpeg,
    selfie,
)

pytestmark = pytest.mark.usefixtures("test_redis")

REASON = "Review: the selfie isn't the face photo's person."


async def _admin(make_user: MakeUser) -> uuid.UUID:
    person, _ = await make_user(Gender.FEMALE)
    person.role = Role.ADMIN
    return person.id


async def _matched(
    db: AsyncSession, storage: FakeStorage, user: User
) -> tuple[Verification, Photo, Photo]:
    """An approved match, as `verify` leaves one, and her main photo matched
    to it for the badge (D-393, D-910): the verification, the selfie and the
    photo."""
    await face_photo(db, storage, user)
    shot = await selfie(db, storage, user, data=jpeg("salmon"))
    shot.status = ReviewStatus.APPROVED
    shot.moderation = {"threshold": rules.MATCH_THRESHOLD, "best": 0.71}
    verification = Verification(
        user_id=user.id,
        challenge="none",
        selfie_photo_id=shot.id,
        status=ReviewStatus.APPROVED,
    )
    db.add(verification)
    await db.flush()
    photo = await approved_photo(db, storage, user)
    photo.moderation = {
        **(photo.moderation or {}),
        service.SELFIE_MATCH: {
            "verification_id": str(verification.id),
            "matched": True,
            "similarity": 0.7,
        },
    }
    user.is_verified = True
    await db.flush()
    return verification, shot, photo


def _pending(db: AsyncSession) -> list[events.Event]:
    pending = db.sync_session.info.get("events.pending", [])
    return [each for _, each in pending]


async def _audits(db: AsyncSession, admin_id: uuid.UUID) -> list[AuditLogEntry]:
    return list(
        await db.scalars(
            select(AuditLogEntry)
            .where(
                AuditLogEntry.actor_id == admin_id,
                AuditLogEntry.action == "verification.undo",
            )
            .execution_options(populate_existing=True)
        )
    )


async def _undo(db: AsyncSession, verification_id: uuid.UUID, by: uuid.UUID) -> Any:
    return await service.undo(db, verification_id, by=by, reason=REASON)


# --- What it does ----------------------------------------------------------------------


async def test_a_woman_goes_back_to_the_selfie_step_without_the_badge(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id = await _admin(make_user)
    woman, token = await make_user(Gender.FEMALE)
    storage = FakeStorage()
    verification, shot, photo = await _matched(db, storage, woman)
    woman_id = woman.id
    assert await repository.shows_badge(db, woman_id)

    undone = await _undo(db, verification.id, admin_id)

    assert (undone.step_before, undone.step_after) == (
        OnboardingStep.DONE,
        OnboardingStep.SELFIE,
    )
    assert (await fresh(db, Verification, verification.id)).status is (
        ReviewStatus.REJECTED
    )
    kept = await fresh(db, Photo, shot.id)
    assert (kept.status, kept.reject_reason) == (ReviewStatus.REJECTED, "undone")
    assert kept.moderation["best"] == 0.71  # the decision's own numbers stay
    assert kept.moderation["review"]["verdict"] == "different"
    assert kept.moderation["undone"]["by"] == str(admin_id)
    assert service.SELFIE_MATCH not in (await fresh(db, Photo, photo.id)).moderation
    her = await fresh(db, User, woman_id)
    assert (her.is_verified, her.onboarding_step) == (False, OnboardingStep.SELFIE)
    assert not await repository.shows_badge(db, woman_id)
    assert (woman_id, events.CLOSE_SOCKETS) in [
        (e.user_id, e.type) for e in _pending(db)
    ]
    [entry] = await _audits(db, admin_id)
    assert (entry.target_type, entry.target_id) == ("user", woman_id)
    assert entry.meta == {
        "reason": REASON,
        "verification_id": str(verification.id),
        "step_before": "done",
        "step_after": "selfie",
        "photos_cleared": 1,
    }
    # Still signed in, at the selfie step, and told only "other".
    me = await client.get("/v1/me", headers=bearer(token))
    assert me.status_code == 200, me.text
    assert me.json()["onboarding_step"] == "selfie"
    latest = await client.get("/v1/verification/latest", headers=bearer(token))
    assert latest.json()["reject_reason"] == "other"


async def test_she_can_take_it_again(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id = await _admin(make_user)
    woman, token = await make_user(Gender.FEMALE)
    verification, _, _ = await _matched(db, FakeStorage(), woman)
    await _undo(db, verification.id, admin_id)

    response = await client.post("/v1/verification/start", headers=bearer(token))

    assert response.status_code in (200, 201), response.text
    assert response.json()["id"] != str(verification.id)
    assert response.json()["status"] == "pending"


async def test_a_man_keeps_done_and_loses_only_the_badge(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-993: his selfie is optional (D-008), so the undo goes no further."""
    admin_id = await _admin(make_user)
    man, _ = await make_user(Gender.MALE)
    verification, _, _ = await _matched(db, FakeStorage(), man)

    undone = await _undo(db, verification.id, admin_id)

    assert undone.step_after is OnboardingStep.DONE
    him = await fresh(db, User, man.id)
    assert (him.is_verified, him.onboarding_step) == (False, OnboardingStep.DONE)
    assert not await repository.shows_badge(db, man.id)
    assert events.CLOSE_SOCKETS not in [e.type for e in _pending(db)]


async def test_a_verdict_already_recorded_different_is_kept(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin_id = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)
    verification, shot, _ = await _matched(db, FakeStorage(), woman)
    earlier = {"verdict": "different", "at": "2026-10-18T09:00:00+00:00"}
    shot.moderation = {**(shot.moderation or {}), "review": earlier}
    await db.flush()

    await _undo(db, verification.id, admin_id)

    assert (await fresh(db, Photo, shot.id)).moderation["review"] == earlier


async def test_her_threads_stay_and_he_may_still_write_d_995(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    admin_id = await _admin(make_user)
    woman, her_token = await make_user(Gender.FEMALE)
    man, his_token = await make_user(Gender.MALE, credits=100)
    verification, _, _ = await _matched(db, FakeStorage(), woman)
    thread = await make_thread(man, woman)
    thread_id = thread.id
    await _undo(db, verification.id, admin_id)

    his = await client.get("/v1/threads", headers=bearer(his_token))
    sent = await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hi"},
        headers=bearer(his_token),
    )
    hers = await client.get("/v1/threads", headers=bearer(her_token))

    assert his.status_code == 200, his.text
    [item] = [i for i in his.json()["items"] if i["id"] == str(thread_id)]
    assert item["other"]["shows_badge"] is False
    assert sent.status_code == 200, sent.text
    assert hers.status_code == 403
    assert error(hers)["code"] == "ONBOARDING_INCOMPLETE"


# --- What it refuses -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (Role.USER, UserStatus.ACTIVE),
        (Role.MODERATOR, UserStatus.ACTIVE),
        (Role.ADMIN, UserStatus.FROZEN),
    ],
)
async def test_only_an_active_admin_undoes_and_nothing_changes_otherwise(
    db: AsyncSession, make_user: MakeUser, role: Role, status: UserStatus
) -> None:
    caller, _ = await make_user(Gender.FEMALE)
    caller.role, caller.status = role, status
    woman, _ = await make_user(Gender.FEMALE)
    verification, _, _ = await _matched(db, FakeStorage(), woman)

    with pytest.raises(service.NotAnAdmin):
        await _undo(db, verification.id, caller.id)

    assert (await fresh(db, User, woman.id)).is_verified is True
    assert (await fresh(db, Verification, verification.id)).status is (
        ReviewStatus.APPROVED
    )


@pytest.mark.parametrize("status", [ReviewStatus.PENDING, ReviewStatus.REJECTED])
async def test_only_an_approved_match_is_undone(
    db: AsyncSession, make_user: MakeUser, status: ReviewStatus
) -> None:
    admin_id = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)
    verification, _, _ = await _matched(db, FakeStorage(), woman)
    verification.status = status
    await db.flush()

    with pytest.raises(service.NotApproved):
        await _undo(db, verification.id, admin_id)

    assert (await fresh(db, User, woman.id)).onboarding_step is OnboardingStep.DONE
    assert await _audits(db, admin_id) == []


async def test_a_match_recorded_same_is_refused_until_recorded_different(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin_id = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)
    verification, shot, _ = await _matched(db, FakeStorage(), woman)
    shot.moderation = {**(shot.moderation or {}), "review": {"verdict": "same"}}
    await db.flush()

    with pytest.raises(service.VerdictSame):
        await _undo(db, verification.id, admin_id)

    assert (await fresh(db, User, woman.id)).is_verified is True
    assert (await fresh(db, Photo, shot.id)).moderation["review"] == {"verdict": "same"}


async def test_a_verification_nobody_holds_is_a_lookup_error(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin_id = await _admin(make_user)

    with pytest.raises(LookupError):
        await _undo(db, uuid.uuid4(), admin_id)


# --- The badge's comparison that straddles an undo ------------------------------------


class _UndoMidCompare(FakeFaceMatch):
    """A comparison during which the undo commits: what `match_photo` read
    first is no longer true when it writes."""

    def __init__(self, db: AsyncSession, verification_id: uuid.UUID, by: uuid.UUID):
        super().__init__()
        self.db, self.verification_id, self.by = db, verification_id, by

    async def compare(self, selfie: bytes, references: Any) -> FaceMatch:
        async with Sessions(self.db)() as session, session.begin():
            await service.undo(session, self.verification_id, by=self.by, reason=REASON)
        return FaceMatch(model="fake", faces_in_selfie=1, similarities=(0.9,))


async def test_a_comparison_running_through_an_undo_writes_no_match(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Else the old match outlives the undo, and `badge_of`, which never asks
    which verification a match came from, would show it again once a new
    selfie is approved (D-993)."""
    admin_id = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)
    storage = FakeStorage()
    verification, _, _ = await _matched(db, storage, woman)
    second = await approved_photo(db, storage, woman, position=1)

    outcome = await service.match_photo(
        Sessions(db),
        second.id,
        storage=storage,
        facematch=_UndoMidCompare(db, verification.id, admin_id),
        settings=make_test_settings(),
    )

    assert outcome == "the selfie was undone while it was compared: left as it is"
    assert service.SELFIE_MATCH not in (await fresh(db, Photo, second.id)).moderation
