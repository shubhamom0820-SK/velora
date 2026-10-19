"""Selfie verification (T-4.5): a selfie compared with the person's face photo
(D-391, T-4.12), on our own worker (D-088), and nothing claimed beyond that.

The API's half: `start` opens a verification, at D-068's `selfie` step or after;
the selfie is uploaded as a photo of kind `selfie` (T-4.2); `submit` attaches
it and queues `verify_selfie`, then wakes the worker (D-261) so the person
isn't left waiting on its 10-second look at the queue; `latest` says how the
newest one went.

The worker's half: `verify`, run by the `verify_selfie` job and by a wake. It
re-encodes the selfie (D-092) and writes it back over itself, compares it with
the face photo's private copy (the bytes moderation scored and wrote back,
never an upload that could have been replaced since), and records the decision
with the user's row locked, once, however many runs reach it. What the
numbers mean is `rules`'; the numbers themselves go in the selfie's
`moderation` record (D-263), and the owner is told only an outcome and a
reason from a list. The public photos are never compared here: a match queues
`match_photo` for each shown photo with a face, for the badge (D-393), and
`match_photo` below is that job's work.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events, images
from app.core.config import Settings
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus, Role, UserStatus
from app.core.errors import AppError
from app.core.images import SNIFF_BYTES, sniff
from app.core.providers.facematch import FaceMatch, FaceMatchProvider
from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.queue import VERIFY_SELFIE, Queue
from app.modules.admin import service as admin_service
from app.modules.onboarding import rules as onboarding_rules
from app.modules.photos import repository as photos_repository
from app.modules.photos.models import Photo
from app.modules.photos.service import MAX_UPLOAD_BYTES, queue_match
from app.modules.referrals import service as referrals_service
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.verification import repository, rules
from app.modules.verification.models import Verification
from app.modules.verification.schemas import Verification as VerificationOut

log = structlog.get_logger(__name__)


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


# --- The API's half -----------------------------------------------------------------


async def start(session: AsyncSession, user: User) -> VerificationOut:
    """A verification waiting for its selfie: the one already open, if there
    is one, else a new one. Not while one is being compared, not once the
    selfie has matched, and not past the day's attempts."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, OnboardingStep.SELFIE)
        if user.is_verified:
            raise AppError(
                "NOT_ALLOWED", "Your selfie already matched your face photo."
            )
        waiting = await repository.pending(session, user.id)
        if any(v.selfie_photo_id is not None for v in waiting):
            raise AppError("NOT_ALLOWED", "Your selfie is being compared already.")
        if waiting:
            return await _out(session, waiting[0])
        await _refuse_past_attempts(session, user.id)
        verification = Verification(user_id=user.id, challenge=rules.NO_CHALLENGE)
        repository.add(session, verification)
        await session.flush()
        return await _out(session, verification)


async def submit(
    session: AsyncSession,
    user: User,
    verification_id: UUID,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    queue: Queue,
    settings: Settings,
) -> VerificationOut:
    """Attach an uploaded selfie and queue its comparison; then wake the worker,
    after the commit, so it finds what it was woken for. Saying it twice with
    the same selfie is once."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, OnboardingStep.SELFIE)
        verification = await repository.for_update(session, user.id, verification_id)
        if verification is None:
            raise _not_found()
        if verification.selfie_photo_id is not None:
            if verification.selfie_photo_id == photo_id:
                return await _out(session, verification)
            raise AppError("NOT_ALLOWED", "This verification has its selfie already.")
        photo = await photos_repository.photo_for_update(session, user.id, photo_id)
        if photo is None or photo.kind is not PhotoKind.SELFIE:
            raise _not_found()
        if photo.status is not ReviewStatus.PENDING:
            raise AppError("NOT_ALLOWED", "Take a new selfie and send that one.")
        if await repository.selfies_submitted(session, [photo.id]):
            raise AppError("NOT_ALLOWED", "Take a new selfie and send that one.")
        await _refuse_past_attempts(session, user.id)
        try:
            await storage.head(settings.R2_BUCKET_PRIVATE, photo.raw_key)
        except ObjectNotFound:
            raise AppError(
                "NOT_ALLOWED", "Upload the selfie before sending it."
            ) from None
        verification.selfie_photo_id = photo.id
        await queue.enqueue(
            VERIFY_SELFIE,
            job_id=f"{VERIFY_SELFIE}:{verification.id}",
            verification_id=str(verification.id),
        )
        out = await _out(session, verification)
    await queue.wake(VERIFY_SELFIE, str(verification.id))
    return out


async def latest(session: AsyncSession, user: User) -> VerificationOut:
    async with session.begin():
        verification = await repository.latest(session, user.id)
        if verification is None:
            raise _not_found()
        return await _out(session, verification)


async def _attempts(session: AsyncSession, user_id: UUID) -> list[datetime]:
    since = clock.now() - rules.ATTEMPT_WINDOW
    return await repository.submitted_since(session, user_id, since)


async def _refuse_past_attempts(session: AsyncSession, user_id: UUID) -> None:
    counted = await _attempts(session, user_id)
    if len(counted) < rules.ATTEMPTS:
        return
    # A place frees when the oldest of the last five leaves the window.
    frees_at = counted[-rules.ATTEMPTS] + rules.ATTEMPT_WINDOW
    wait = max(1, math.ceil((frees_at - clock.now()).total_seconds()))
    raise AppError(
        "RATE_LIMITED",
        f"You can send {rules.ATTEMPTS} selfies a day. Try again later.",
        status=429,
        details={"retry_after_s": wait},
    )


async def _out(session: AsyncSession, verification: Verification) -> VerificationOut:
    reason = None
    if (
        verification.status is ReviewStatus.REJECTED
        and verification.selfie_photo_id is not None
    ):
        selfie = await photos_repository.photo_by_id(
            session, verification.selfie_photo_id
        )
        reason = rules.owner_reason(selfie.reject_reason if selfie else None)
    attempts = await _attempts(session, verification.user_id)
    return VerificationOut(
        id=verification.id,
        status=verification.status,
        submitted=verification.selfie_photo_id is not None,
        reject_reason=reason,
        attempts_left=max(0, rules.ATTEMPTS - len(attempts)),
    )


# --- The worker's half ----------------------------------------------------------------

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]

# How long a job waits before its next try, by what it waits for.
NOT_SUBMITTED_YET: Final = timedelta(seconds=5)
PHOTOS_WAITING: Final = timedelta(seconds=20)
STORAGE_FAILED: Final = timedelta(seconds=10)

# In a shown photo's `moderation` record: its comparison with the kept selfie.
SELFIE_MATCH: Final = "selfie_match"


class TryAgain(Exception):
    """Not decidable yet. The `verify_selfie` job tries again after `defer`;
    its last try records `final` (if any) rather than leave the person stuck
    waiting. A wake leaves it to the job."""

    def __init__(
        self,
        event: str,
        what: str,
        *,
        defer: timedelta,
        final: rules.Reason | None,
    ) -> None:
        super().__init__(what)
        self.event = event
        self.defer = defer
        self.final = final


@dataclass(frozen=True)
class _Compared:
    match: FaceMatch | None
    references: tuple[Photo, ...]
    width: int | None = None
    height: int | None = None


async def verify(
    sessions: Sessions,
    verification_id: UUID,
    *,
    storage: StorageProvider,
    facematch: FaceMatchProvider,
    queue: Queue,
    settings: Settings,
    via: str,
) -> str:
    """Compare one submitted selfie with the face photo and decide, once: what
    happened, in words. `via` is `wake` or `queue`, recorded with the decision."""
    async with sessions() as session, session.begin():
        verification = await repository.by_id(session, verification_id)
        selfie: Photo | None = None
        references: list[Photo] = []
        waiting = False
        if verification is not None and verification.selfie_photo_id is not None:
            selfie = await photos_repository.photo_by_id(
                session, verification.selfie_photo_id
            )
            face = await repository.face_photo(session, verification.user_id)
            references = [face] if face is not None else []
            waiting = await repository.face_photo_waiting(session, verification.user_id)
    if verification is None:
        return "no such verification: its user was refused, and it went with them"
    if verification.status is not ReviewStatus.PENDING:
        return f"already {verification.status.value}: nothing to do"
    if selfie is None:
        # Queued before its submit committed, or never committed at all.
        raise TryAgain(
            "verification.not_submitted",
            "no selfie submitted yet",
            defer=NOT_SUBMITTED_YET,
            final=None,
        )
    if not references and waiting:
        raise TryAgain(
            "verification.photos_waiting",
            "the face photo is still being checked",
            defer=PHOTOS_WAITING,
            final=rules.NO_PHOTOS,
        )
    done = Recorder(sessions, verification, selfie, via, storage, settings, queue)
    if not references:
        return await done(rules.NO_PHOTOS, _Compared(None, ()))

    private = settings.R2_BUCKET_PRIVATE
    try:
        data = await storage.read_prefix(private, selfie.raw_key, MAX_UPLOAD_BYTES + 1)
    except ObjectNotFound:
        return await done(rules.UNREADABLE, _Compared(None, ()))
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise _storage_failed(error) from None
    image_type = sniff(data[:SNIFF_BYTES])
    try:
        if image_type is None or len(data) > MAX_UPLOAD_BYTES:
            raise images.UnreadableImage
        clean = images.reencode(data, image_type)
    except images.UnreadableImage:
        outcome = await done(rules.UNREADABLE, _Compared(None, ()))
        await storage.delete(private, selfie.raw_key)
        return outcome
    del data
    # Written back over itself before anything else, so no original with its
    # location is kept, whatever happens next (D-092).
    await _stored(storage.put_bytes(private, selfie.raw_key, clean.data, "image/jpeg"))

    read = await asyncio.gather(
        *(_reference_copy(storage, settings, photo) for photo in references)
    )
    found = [(photo, ref) for photo, ref in zip(references, read, strict=True) if ref]
    if not found:
        return await done(rules.NO_PHOTOS, _Compared(None, ()))
    match = await facematch.compare(clean.data, [ref for _, ref in found])
    compared = _Compared(
        match, tuple(photo for photo, _ in found), clean.width, clean.height
    )
    return await done(rules.decide(match), compared)


async def give_up(
    sessions: Sessions,
    verification_id: UUID,
    reason: rules.Reason,
    *,
    storage: StorageProvider,
    settings: Settings,
    via: str,
) -> str:
    """The job's last try failed: reject, so the person can start again rather
    than wait on a comparison that won't come. Only a submitted, pending one."""
    async with sessions() as session, session.begin():
        verification = await repository.by_id(session, verification_id)
        selfie = None
        if verification is not None and verification.selfie_photo_id is not None:
            selfie = await photos_repository.photo_by_id(
                session, verification.selfie_photo_id
            )
    if verification is None or selfie is None:
        return "nothing submitted: nothing to give up on"
    done = Recorder(sessions, verification, selfie, via, storage, settings)
    return await done(reason, _Compared(None, ()))


async def _reference_copy(
    storage: StorageProvider, settings: Settings, photo: Photo
) -> bytes | None:
    """The face photo's private copy: the bytes moderation scored and wrote
    back over the upload itself (T-4.4, D-092). None if it has gone."""
    try:
        return await storage.read_prefix(
            settings.R2_BUCKET_PRIVATE, photo.raw_key, MAX_UPLOAD_BYTES + 1
        )
    except ObjectNotFound:
        return None
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise _storage_failed(error) from None


@dataclass(frozen=True)
class Recorder:
    """Writes one verification's decision; `queue` takes the badge's
    comparisons a match sets off (None where nothing can be approved)."""

    sessions: Sessions
    verification: Verification
    selfie: Photo
    via: str
    storage: StorageProvider
    settings: Settings
    queue: Queue | None = None

    async def __call__(self, reason: rules.Reason | None, compared: _Compared) -> str:
        return await _record(self, reason, compared)


async def _record(
    to: Recorder, reason: rules.Reason | None, compared: _Compared
) -> str:
    """Write the decision with the user's row locked, unless it stopped
    waiting for one: once, whoever gets here first."""
    verification, selfie, via = to.verification, to.selfie, to.via
    async with to.sessions() as session, session.begin():
        try:
            user = await users_service.locked_user(session, verification.user_id)
            locked = await repository.for_update(session, user.id, verification.id)
            photo = await photos_repository.photo_for_update(
                session, user.id, selfie.id
            )
        except LookupError:
            locked = photo = None
        if locked is None or photo is None:
            # Refused while this ran: the rows went, and D-078's deletion may
            # have run before the copy above was written back. Don't leave it.
            await to.storage.delete(to.settings.R2_BUCKET_PRIVATE, selfie.raw_key)
            return "its user was refused while it was compared: its selfie removed"
        if locked.status is not ReviewStatus.PENDING:
            return f"{locked.status.value} while it was compared: left as it is"
        photo.moderation = _summary(compared, via)
        if compared.width is not None:
            photo.width, photo.height = compared.width, compared.height
        to_compare: list[Photo] = []
        if reason is None:
            locked.status = ReviewStatus.APPROVED
            photo.status = ReviewStatus.APPROVED
            user.is_verified = True
            # A referral's reward, if this is its first trigger (T-8.6).
            await referrals_service.reward(session, user.id, "selfie")
            # D-393: the photos already shown, each with a face, compared with
            # this selfie for the badge, once this decision is committed.
            to_compare = await repository.shown_photos_with_a_face(session, user.id)
        else:
            locked.status = ReviewStatus.REJECTED
            photo.status = ReviewStatus.REJECTED
            photo.reject_reason = reason
    outcome = reason or ReviewStatus.APPROVED.value
    log.info(
        "verification.decided",
        verification_id=str(verification.id),
        outcome=outcome,
        via=via,
    )
    if to.queue is not None:
        for shown in to_compare:
            await queue_match(to.queue, shown)
    return outcome


def _summary(compared: _Compared, via: str) -> dict[str, Any]:
    """The selfie's `moderation` record (D-263): the numbers the decision read,
    exactly, and which photos they came from; never an image, a key or a URL."""
    record: dict[str, Any] = {
        "threshold": rules.MATCH_THRESHOLD,
        "decided_by": via,
    }
    match = compared.match
    if match is not None:
        record |= {
            "provider": match.model,
            "faces": match.faces_in_selfie,
            "best": match.best,
            "compared": [
                {"photo_id": str(photo.id), "similarity": similarity}
                for photo, similarity in zip(
                    compared.references, match.similarities, strict=True
                )
            ],
        }
    return record


def _storage_failed(error: Exception) -> TryAgain:
    return TryAgain(
        "verification.storage_failed",
        type(error).__name__,
        defer=STORAGE_FAILED,
        final=rules.UNAVAILABLE,
    )


async def _stored(write: Awaitable[None]) -> None:
    try:
        await write
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise _storage_failed(error) from None


# --- The badge's comparison (T-4.12, D-393) --------------------------------------------
#
# `match_photo`, run by the job of that name: one approved public photo with a
# face, compared with the kept selfie, the result written into that photo's
# `moderation` record and never a rejection. Queued when the photo is approved
# (a selfie already kept) and when the selfie is decided (photos already there),
# and by `show_face_photo` for the copy it makes. The badge (`repository.
# shows_badge`) reads these records; nobody waits on one, so no wake.


async def match_photo(
    sessions: Sessions,
    photo_id: UUID,
    *,
    storage: StorageProvider,
    facematch: FaceMatchProvider,
    settings: Settings,
) -> str:
    """Compare one shown photo with the kept selfie, once: what happened, in
    words. Nothing about the person is decided here: a photo that doesn't match
    stays on the profile and doesn't count toward the badge."""
    async with sessions() as session, session.begin():
        photo = await photos_repository.photo_by_id(session, photo_id)
        kept = None
        if photo is not None:
            kept = await repository.kept_selfie(session, photo.user_id)
    if photo is None:
        return "no such photo: its user was refused, and it went with them"
    if (
        photo.kind is not PhotoKind.PUBLIC
        or photo.status is not ReviewStatus.APPROVED
        or photo.public_key is None
    ):
        return "not a shown photo: nothing to compare"
    record = photo.moderation or {}
    if not record.get("faces"):
        return "no face in it: nothing to compare"
    if kept is None:
        return "no selfie kept: nothing to compare with"
    verification, selfie = kept
    already = record.get(SELFIE_MATCH) or {}
    if already.get("verification_id") == str(verification.id):
        return "already compared: nothing to do"

    try:
        selfie_bytes = await storage.read_prefix(
            settings.R2_BUCKET_PRIVATE, selfie.raw_key, MAX_UPLOAD_BYTES + 1
        )
        shown_bytes = await storage.read_prefix(
            settings.R2_BUCKET_PUBLIC, photo.public_key, MAX_UPLOAD_BYTES + 1
        )
    except ObjectNotFound:
        return "a file is gone: left as it is"
    except Exception as error:  # noqa: BLE001 — storage is down: try again
        raise _storage_failed(error) from None
    match = await facematch.compare(selfie_bytes, [shown_bytes])
    similarity = match.similarities[0] if match.similarities else None
    matched = similarity is not None and similarity >= rules.MATCH_THRESHOLD

    async with sessions() as session, session.begin():
        try:
            user = await users_service.locked_user(session, photo.user_id)
            locked = await photos_repository.photo_for_update(
                session, user.id, photo.id
            )
        except LookupError:
            locked = None
        if locked is None or locked.status is not ReviewStatus.APPROVED:
            return "no longer shown while it was compared: left as it is"
        # P-163: an undo while this compared leaves nothing to vouch for; its
        # match written now would outlive it, and `badge_of` doesn't ask which
        # verification a match came from.
        still = await repository.kept_selfie(session, user.id)
        if still is None or still[0].id != verification.id:
            return "the selfie was undone while it was compared: left as it is"
        locked.moderation = {
            **(locked.moderation or {}),
            SELFIE_MATCH: {
                "verification_id": str(verification.id),
                "provider": match.model,
                "similarity": similarity,
                "threshold": rules.MATCH_THRESHOLD,
                "matched": matched,
                "decided_by": "queue",
                "at": clock.now().isoformat(),
            },
        }
    outcome = "matched" if matched else "no_match"
    log.info("badge.compared", photo_id=str(photo.id), outcome=outcome)
    return outcome


# --- The founder's review (D-264) -------------------------------------------------------
#
# Until the threshold is measured (P-160), a person looks at every decision:
# face matching alone doesn't stop a man with a woman's photos and one real
# selfie of her, which matches her photos closely, nowhere near the threshold.
# `app/tools/selfie_review.py` lists what to look at; the verdicts written here,
# same person or not, are the measurement P-160 needs, gathered from real
# decisions as they are made.


@dataclass(frozen=True)
class Compared:
    photo_id: str
    similarity: float | None
    # The face photo's private key (`face`), a shown photo's public key
    # (`shown`); None once the file is gone.
    key: str | None


@dataclass(frozen=True)
class ForReview:
    verification_id: UUID
    decided_at: datetime
    gender: str | None
    outcome: str  # approved, or the reason it was rejected
    best: float | None
    threshold: float | None
    near: bool
    mixed: bool
    verdict: str | None
    selfie_key: str
    # The face photo the selfie was compared with (D-391); None if none was.
    face: Compared | None
    # The shown photos compared with the selfie for the badge (D-393), by place.
    shown: tuple[Compared, ...]


async def for_review(
    sessions: Sessions, since: datetime, *, include_reviewed: bool = False
) -> list[ForReview]:
    """Every decision since `since` the founder hasn't given a verdict on
    (all of them, with `include_reviewed`), newest first, each with the face
    photo it was compared with and the shown photos compared with it since. The
    seed's aren't decisions, so they aren't listed."""
    async with sessions() as session, session.begin():
        rows = await repository.decided_since(session, since)
        wanted = {
            UUID(c["photo_id"])
            for _, selfie, _ in rows
            for c in (selfie.moderation or {}).get("compared", [])
        }
        photos = {p.id: p for p in await repository.photos_by_id(session, list(wanted))}
        shown_by_user = {
            verification.user_id: await repository.shown_photos_with_a_face(
                session, verification.user_id
            )
            for verification, _, _ in rows
        }
    found: list[ForReview] = []
    for verification, selfie, gender in rows:
        record = selfie.moderation or {}
        if record.get("decided_by") == "seed":
            continue
        verdict = (record.get("review") or {}).get("verdict")
        if verdict is not None and not include_reviewed:
            continue
        face = next(
            (
                Compared(
                    photo_id=c["photo_id"],
                    similarity=c["similarity"],
                    key=getattr(photos.get(UUID(c["photo_id"])), "raw_key", None),
                )
                for c in record.get("compared", [])
            ),
            None,
        )
        shown = tuple(
            Compared(
                photo_id=str(photo.id),
                similarity=(photo.moderation or {})[SELFIE_MATCH].get("similarity"),
                key=photo.public_key,
            )
            for photo in shown_by_user[verification.user_id]
            if ((photo.moderation or {}).get(SELFIE_MATCH) or {}).get("verification_id")
            == str(verification.id)
        )
        approved = verification.status is ReviewStatus.APPROVED
        best = record.get("best")
        found.append(
            ForReview(
                verification_id=verification.id,
                decided_at=verification.updated_at,
                gender=None if gender is None else gender.value,
                outcome="approved"
                if approved
                else (selfie.reject_reason or "rejected"),
                best=best,
                threshold=record.get("threshold"),
                near=rules.near_the_threshold(best),
                mixed=rules.mixed(approved, [c.similarity for c in shown]),
                verdict=verdict,
                selfie_key=selfie.raw_key,
                face=face,
                shown=shown,
            )
        )
    return found


async def record_verdict(
    sessions: Sessions, verification_id: UUID, verdict: rules.Verdict
) -> bool:
    """Write the founder's verdict into the selfie's record: whether the
    selfie and the face photo show the same person. Changes nothing else:
    undoing a decision is `undo`'s (P-163). False if there is no such
    verification."""
    async with sessions() as session, session.begin():
        selfie = await repository.selfie_of(session, verification_id)
        if selfie is None:
            return False
        selfie.moderation = {
            **(selfie.moderation or {}),
            "review": {"verdict": verdict, "at": clock.now().isoformat()},
        }
    log.info(
        "verification.reviewed", verification_id=str(verification_id), verdict=verdict
    )
    return True


# --- Undoing a match the review found wrong (P-163, D-993, D-995, D-1051) ---------------

UNDO: Final = "verification.undo"


class NotAnAdmin(Exception):
    """`by` isn't an active admin: nothing changed."""


class NotApproved(Exception):
    """Only an approved verification is undone: nothing changed."""

    def __init__(self, status: ReviewStatus) -> None:
        super().__init__(status.value)
        self.status = status


class VerdictSame(Exception):
    """The founder recorded `same` for it: an undo would contradict the
    record P-160 measures with, so it is recorded `different` first."""


@dataclass(frozen=True)
class Undone:
    user_id: UUID
    step_before: OnboardingStep
    step_after: OnboardingStep
    photos_cleared: int


async def undo(
    session: AsyncSession, verification_id: UUID, *, by: UUID, reason: str
) -> Undone:
    """Undo an approved selfie match, in the caller's transaction (D-993): the
    verification and its selfie rejected (`undone`), `is_verified` cleared, and
    every `selfie_match` this selfie gave a photo removed, so no badge outlives
    it. Someone whose finishing needs a match goes back to the `selfie` step
    and their sockets close; they stay signed in, to take it again. A man keeps
    `done`: for him only the badge goes. Threads are left as they are (D-995),
    and a referral's reward stays paid. The verdict is recorded `different`
    where none is; a recorded `same` is `VerdictSame`. One `audit_log` row as
    `by`, an active admin. LookupError if there is no such verification."""
    admin = await _active_admin(session, by)
    found = await repository.by_id(session, verification_id)
    if found is None:
        raise LookupError("no such verification")
    user = await users_service.locked_user(session, found.user_id)
    verification = await repository.for_update(session, user.id, verification_id)
    if verification is None or verification.selfie_photo_id is None:
        raise LookupError("no such verification")
    if verification.status is not ReviewStatus.APPROVED:
        raise NotApproved(verification.status)
    selfie = await photos_repository.photo_for_update(
        session, user.id, verification.selfie_photo_id
    )
    if selfie is None:
        raise LookupError("no such selfie")
    record = selfie.moderation or {}
    review = record.get("review") or {}
    if review.get("verdict") == "same":
        raise VerdictSame
    now = clock.now()

    verification.status = ReviewStatus.REJECTED
    selfie.status = ReviewStatus.REJECTED
    selfie.reject_reason = rules.UNDONE
    selfie.moderation = {
        **record,
        "review": review or {"verdict": "different", "at": now.isoformat()},
        "undone": {"by": str(admin.id), "at": now.isoformat()},
    }
    user.is_verified = False
    matched = await repository.photos_matched_by(session, user.id, verification.id)
    for photo in matched:
        photo.moderation = {
            key: value
            for key, value in (photo.moderation or {}).items()
            if key != SELFIE_MATCH
        }
    before = user.onboarding_step
    if onboarding_rules.needs_a_match(user.gender) and before is OnboardingStep.DONE:
        user.onboarding_step = OnboardingStep.SELFIE
        events.close_sockets(session, user.id)
    await admin_service.audit(
        session,
        admin.id,
        UNDO,
        {
            "reason": reason,
            "verification_id": str(verification.id),
            "step_before": before.value,
            "step_after": user.onboarding_step.value,
            "photos_cleared": len(matched),
        },
        target=("user", user.id),
    )
    log.info(
        "verification.undone",
        verification_id=str(verification.id),
        step_after=user.onboarding_step.value,
    )
    return Undone(
        user_id=user.id,
        step_before=before,
        step_after=user.onboarding_step,
        photos_cleared=len(matched),
    )


async def _active_admin(session: AsyncSession, user_id: UUID) -> User:
    try:
        admin = await users_service.locked_user(session, user_id)
    except LookupError:
        raise NotAnAdmin from None
    if admin.role is not Role.ADMIN or admin.status is not UserStatus.ACTIVE:
        raise NotAnAdmin
    return admin
