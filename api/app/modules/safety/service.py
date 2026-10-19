"""Safety records (T-4.4 starts it): signals about a person, never verdicts.
Reports and blocks (T-9.1).

`fraud_events` holds signals for T-9.2's scoring and T-9.5's queue. A signal is
what something observed, and is recorded as exactly that.

**A block is total and silent** (06-TESTING's critical 9, D-862). Every read
asks `blocked_either_way`, so from the moment it commits neither person
appears to the other anywhere, and everything between them answers
`NOT_FOUND`, the same as an id nobody holds: never `BLOCKED`, which would tell
the blocked person. It holds against the blocked person's number, so a new
account on it is still blocked (D-861). Unblocking lifts it and keeps the row
(D-860). Grants between them are revoked with it; nothing else is touched, so
unblocking brings every Thread back as it was, a clearing still in place.

**A report** goes to moderation, and its subject is never told: nothing is
queued or written for them, here or by anything this calls. Its evidence is
the whole Thread (`report_evidence`), whatever the reporter cleared.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Subquery

from app.core import clock
from app.core.config import Settings
from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.core.queue import Queue
from app.core.storage_keys import public_url
from app.modules.album import service as album_service
from app.modules.discovery import rules as discovery_rules
from app.modules.messages.models import Message
from app.modules.notifications import service as notifications_service
from app.modules.notifications.rules import Kind
from app.modules.safety import fraud, repository, schemas, scoring, signals
from app.modules.safety.models import FraudEvent, Report
from app.modules.threads.schemas import CardLite
from app.modules.users.models import User

# D-093: a model's score that one photo may show a minor. The name and the
# record say so; nothing downstream may read it as a fact about the person.
POSSIBLE_MINOR_SCORE: Final = fraud.POSSIBLE_MINOR_SCORE
POSSIBLE_MINOR_NOTE: Final = (
    "A model's score for one photo, not a finding about the person (D-093)."
)
# T-9.2 (D-900): it weighs in the score, capped under the monitor band, so it
# never acts on anyone alone; repeated flags go to a human, never to an
# automatic action (D-093, P-72).
POSSIBLE_MINOR_WEIGHT: Final = fraud.WEIGHTS[fraud.POSSIBLE_MINOR_SCORE]

# T-7.3, D-030: a message refused for a rule. The rule's name only, never the
# text (CLAUDE.md rule 15). Worth what its rule is (T-9.2, D-900).
MESSAGE_REJECTED: Final = fraud.MESSAGE_REJECTED


def record_possible_minor(
    session: AsyncSession, user_id: UUID, *, score: float, model: str
) -> None:
    """D-093's minimal record, in the caller's transaction: who, when (the
    row's `created_at`), the score and the model. Never the image, nor which
    photo: the image is deleted, and the record outlives it."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id,
            signal=POSSIBLE_MINOR_SCORE,
            weight=POSSIBLE_MINOR_WEIGHT,
            meta={"what": POSSIBLE_MINOR_NOTE, "model": model, "score": score},
        ),
    )


def minor_flags_tally() -> Subquery:
    """Everyone's possible-minor flags waiting for a human, as a subquery
    (`repository.minor_flags_awaiting`'s columns): T-9.5's list reads it."""
    return repository.minor_flags_awaiting(
        POSSIBLE_MINOR_SCORE,
        fraud.MINOR_REVIEWED,
        since=clock.now() - fraud.MINOR_FLAGS_WINDOW,
        at_least=fraud.MINOR_FLAGS_TO_REVIEW,
    )


async def minor_flags_awaiting(session: AsyncSession, user_id: UUID) -> Row[Any] | None:
    """`user_id`'s possible-minor flags waiting for a human, or None: two or
    more in 30 days, after any decision on them (D-991, D-1050)."""
    return await repository.minor_flags_of(
        session,
        user_id,
        POSSIBLE_MINOR_SCORE,
        fraud.MINOR_REVIEWED,
        since=clock.now() - fraud.MINOR_FLAGS_WINDOW,
        at_least=fraud.MINOR_FLAGS_TO_REVIEW,
    )


async def escalate_possible_minor(session: AsyncSession, user_id: UUID) -> None:
    """After a flag is recorded, in its transaction (D-991): the flag that puts
    the person on the admins' list tells every active admin; a later one, while
    they still wait, brings each admin's in-app row up to date and pushes
    nothing (P-72). Nothing here acts on the person."""
    tally = await minor_flags_awaiting(session, user_id)
    if tally is None:
        return
    payload = {
        "subject_id": str(user_id),
        "flags": tally.flags,
        "scores": list(tally.scores),
        "first_at": tally.first_at.isoformat(),
        "last_at": tally.last_at.isoformat(),
    }
    # One fewer, a moment ago, was off the list: this flag is the one that put
    # them on it.
    if tally.flags == fraud.MINOR_FLAGS_TO_REVIEW:
        await notifications_service.notify_admins(session, Kind.MINOR_FLAGS, payload)
    else:
        await notifications_service.update_admins(
            session, Kind.MINOR_FLAGS, "subject_id", payload
        )


# D-520: a chargeback whose Velas were spent before they could be taken back.
# What happened to the money, not a judgement of him: a dispute may be his
# bank's mistake, and freezing is a moderation decision, never automatic.
CHARGEBACK_SHORTFALL: Final = fraud.CHARGEBACK_SHORTFALL
CHARGEBACK_SHORTFALL_NOTE: Final = (
    "A dispute took back money whose Velas were spent: the Velas it couldn't "
    "take back (D-520)."
)
# T-9.2 (D-900): capped at monitor, so a chargeback never freezes on its own (D-520).
CHARGEBACK_SHORTFALL_WEIGHT: Final = fraud.WEIGHTS[fraud.CHARGEBACK_SHORTFALL]


def record_chargeback_shortfall(
    session: AsyncSession, user_id: UUID, *, payment_id: UUID, shortfall: int
) -> None:
    """In the caller's transaction: our payment's id and the Velas short."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id,
            signal=CHARGEBACK_SHORTFALL,
            weight=CHARGEBACK_SHORTFALL_WEIGHT,
            meta={
                "what": CHARGEBACK_SHORTFALL_NOTE,
                "payment_id": str(payment_id),
                "shortfall": shortfall,
            },
        ),
    )


def record_message_rejected(session: AsyncSession, user_id: UUID, *, rule: str) -> None:
    """A message `user_id` tried to send, refused for `rule`, in the caller's
    transaction: who, when and which rule. Never the message."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id,
            signal=MESSAGE_REJECTED,
            weight=fraud.rejected_weight(rule),
            meta={"rule": rule},
        ),
    )


# --- Blocks (T-9.1) ------------------------------------------------------------------

BLOCKS_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


def _not_found() -> AppError:
    """An id nobody holds (04-API)."""
    return AppError("NOT_FOUND", "Not found.", status=404)


def _not_yourself(what: str) -> AppError:
    return AppError(
        "NOT_ALLOWED",
        f"You can't {what} yourself.",
        status=422,
        details={"why": "yourself"},
    )


async def _target(session: AsyncSession, user: User, other_id: UUID, what: str) -> None:
    """Anyone with an account, in any status, visible to `user` or not: a
    block or a report needs no permission to see them. Yourself is
    `NOT_ALLOWED`; an id nobody holds, `NOT_FOUND`."""
    if other_id == user.id:
        raise _not_yourself(what)
    if not await repository.user_exists(session, other_id):
        raise _not_found()


async def _block_in(session: AsyncSession, user: User, other_id: UUID) -> list[UUID]:
    """The block and its grants' revocation, in the caller's transaction. The
    album requests whose copies must go, once committed."""
    await repository.add_block(session, user.id, other_id)
    return await album_service.revoke_between(session, user.id, other_id)


async def block(
    session: AsyncSession,
    user: User,
    other_id: UUID,
    *,
    queue: Queue,
    settings: Settings,
) -> schemas.BlockedUser:
    """`POST /blocks`: `other_id` blocked by `user`, and any grant between them
    revoked. Twice is once. Nothing is queued or written for them."""
    async with session.begin():
        await _target(session, user, other_id, "block")
        revoked = await _block_in(session, user, other_id)
        row = await repository.standing_block(session, user.id, other_id)
    await album_service.delete_revoked_copies(queue, revoked)
    return _blocked_user(row, clock.now(), settings)


async def unblock(session: AsyncSession, user: User, other_id: UUID) -> None:
    """`DELETE /blocks/{user_id}`: lifted and kept (D-860). Someone never
    blocked, or unblocked already, is the same 204."""
    async with session.begin():
        await repository.lift_block(session, user.id, other_id, clock.now())


async def blocks(
    session: AsyncSession, user: User, *, params: PageParams, settings: Settings
) -> schemas.BlockedUserPage:
    """`GET /blocks`: whom `user` blocks now, newest first. Never who blocks
    them: that is never told."""
    after = None if params.cursor is None else BLOCKS_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.standing_blocks(
            session, user.id, after=after, limit=params.fetch
        )
    now = clock.now()
    return schemas.BlockedUserPage.of(
        [_blocked_user(row, now, settings) for row in rows],
        params,
        lambda item: BLOCKS_CURSOR.encode((item.blocked_at, item.user.id)),
    )


def _blocked_user(row: Any, now: datetime, settings: Settings) -> schemas.BlockedUser:
    """The blocked person as a card, as a Thread's row shows the other person:
    a deleted account has no name, username or photo (D-051, D-500)."""
    deleted = row.blocked_status is UserStatus.DELETED
    return schemas.BlockedUser(
        user=CardLite(
            id=row.Block.blocked_id,
            first_name=None if deleted else row.blocked_first_name,
            username=None if deleted else row.blocked_username,
            main_photo_url=None
            if deleted or row.blocked_photo_key is None
            else public_url(settings, row.blocked_photo_key),
            shows_badge=not deleted and bool(row.blocked_badge),
            is_online=not deleted
            and row.blocked_last_active_at is not None
            and row.blocked_last_active_at >= now - discovery_rules.ONLINE_FOR,
            deleted=deleted,
        ),
        blocked_at=row.Block.created_at,
    )


# --- Reports (T-9.1) -----------------------------------------------------------------


async def report(
    session: AsyncSession,
    user: User,
    body: schemas.FileReportRequest,
    *,
    queue: Queue,
) -> schemas.ReportFiled:
    """`POST /reports`: one row for moderation, and with `also_block` the block
    too, in one transaction. Anyone with an account may be reported, a block
    standing either way or not, so the answer never says whether one does.
    `thread_id`, when given, is the pair's own Thread or `NOT_FOUND`. Every
    refusal comes before anything is written. Reporting the same person again
    is a new report (D-863). Their subject is never told."""
    revoked: list[UUID] = []
    async with session.begin():
        await _target(session, user, body.reported_id, "report")
        if body.thread_id is not None:
            pair = await repository.pair_thread_id(session, user.id, body.reported_id)
            if pair != body.thread_id:
                raise _not_found()
        filed = await repository.add_report(
            session,
            Report(
                reporter_id=user.id,
                reported_id=body.reported_id,
                reason=body.reason,
                details=body.details,
                thread_id=body.thread_id,
            ),
        )
        if body.also_block:
            revoked = await _block_in(session, user, body.reported_id)
        # T-9.2: a signal, and the score at once, so three reports in 24 hours
        # freeze in the third one's transaction (D-031, D-901).
        signals.record_report_received(
            session, body.reported_id, report_id=filed.id, reason=body.reason
        )
        await scoring.recompute(session, body.reported_id)
        result = schemas.ReportFiled(id=filed.id, created_at=filed.created_at)
    await album_service.delete_revoked_copies(queue, revoked)
    return result


REPORTS_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


async def filed_reports(
    session: AsyncSession, user: User, *, params: PageParams, settings: Settings
) -> schemas.FiledReportPage:
    """`GET /reports`: the reports `user` filed, newest first. Never one about
    them (T-9.1: never told), and never a status (D-911)."""
    after = None if params.cursor is None else REPORTS_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.filed_reports(
            session, user.id, after=after, limit=params.fetch
        )
    now = clock.now()
    return schemas.FiledReportPage.of(
        [_filed_report(row, now, settings) for row in rows],
        params,
        lambda item: REPORTS_CURSOR.encode((item.created_at, item.id)),
    )


def _filed_report(row: Any, now: datetime, settings: Settings) -> schemas.FiledReport:
    """The reported person as a card: a deleted account is `deleted` and
    nothing more (D-051, D-500); across a block, either way, their name and
    username alone, the same whoever blocked (D-911)."""
    deleted = row.reported_status is UserStatus.DELETED
    shown = not deleted and not row.blocked
    return schemas.FiledReport(
        id=row.id,
        reason=row.reason,
        created_at=row.created_at,
        reported=CardLite(
            id=row.reported_id,
            first_name=None if deleted else row.reported_first_name,
            username=None if deleted else row.reported_username,
            main_photo_url=public_url(settings, row.reported_photo_key)
            if shown and row.reported_photo_key is not None
            else None,
            shows_badge=shown and bool(row.reported_badge),
            is_online=shown
            and row.reported_last_active_at is not None
            and row.reported_last_active_at >= now - discovery_rules.ONLINE_FOR,
            deleted=deleted,
        ),
    )


async def report_evidence(session: AsyncSession, report_id: UUID) -> Sequence[Message]:
    """The report's Thread, every message of it, oldest first, in the caller's
    transaction (T-9.5 reads through this): what either person cleared
    included, `body_raw` included. No Thread named: nothing."""
    thread_id = await repository.report_thread_id(session, report_id)
    if thread_id is None:
        return []
    return await repository.thread_messages(session, thread_id)
