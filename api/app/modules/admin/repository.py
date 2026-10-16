"""SQL for the ops tables. No rules here: the services decide."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    Row,
    Select,
    case,
    func,
    insert,
    or_,
    select,
    true,
    tuple_,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import BanKind, PhotoKind, ReportStatus, ReviewStatus, UserStatus
from app.modules.admin.models import AppConfig, AuditLogEntry
from app.modules.auth.models import BannedIdentity
from app.modules.messages.models import Message
from app.modules.payments.models import RefundRequest
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from app.modules.safety.models import FraudEvent, FraudScore, Report
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet

# The system user's id (D-905), which `admin.service.SYSTEM_USER_ID` names:
# here, so the panel's queries can leave it out without importing the service.
SYSTEM_USER_ID: Final = UUID("00000000-0000-4000-8000-000000000001")


async def config_value(session: AsyncSession, key: str) -> Any | None:
    """`app_config.value` for `key`, decoded from JSON, or None if no row."""
    return await session.scalar(select(AppConfig.value).where(AppConfig.key == key))


async def add_audit(
    session: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    meta: dict[str, Any] | None,
    target: tuple[str, UUID] | None = None,
) -> UUID:
    target_type, target_id = target if target is not None else (None, None)
    added = await session.scalar(
        insert(AuditLogEntry)
        .values(
            actor_id=actor_id,
            action=action,
            meta=meta,
            target_type=target_type,
            target_id=target_id,
        )
        .returning(AuditLogEntry.id)
    )
    assert added is not None  # an insert returns its row
    return added


# --- The panel's reads (T-9.5) ---------------------------------------------------------
# Each list is ordered and keyed as 04-API says, and fetches `limit + 1` rows
# (D-270). Nothing here decides who may see what: the service does.

_Key = tuple[datetime, UUID]


def _profile_columns() -> tuple[Any, ...]:
    return (Profile.first_name, Profile.username, Profile.city)


async def users_page(
    session: AsyncSession,
    *,
    phone_hash: str | None = None,
    user_id: UUID | None = None,
    prefix: str | None = None,
    after: _Key | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Accounts, newest first by `(created_at, id)`, never the system user
    (D-905). At most one filter: a number's hash, matched exactly, every row it
    ever had included, an erased one too (D-061, D-500); an id; or a username
    or first name starting with `prefix`, a LIKE pattern already escaped."""
    query = (
        select(User, *_profile_columns())
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(User.id != SYSTEM_USER_ID)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(limit)
    )
    if phone_hash is not None:
        query = query.where(User.phone_hash == phone_hash)
    if user_id is not None:
        query = query.where(User.id == user_id)
    if prefix is not None:
        query = query.where(
            or_(
                Profile.username.ilike(prefix, escape="\\"),
                Profile.first_name.ilike(prefix, escape="\\"),
            )
        )
    if after is not None:
        query = query.where(tuple_(User.created_at, User.id) < after)
    return (await session.execute(query)).all()


async def user_row(session: AsyncSession, user_id: UUID) -> Row[Any] | None:
    """One account and its profile's names, never the system user."""
    if user_id == SYSTEM_USER_ID:
        return None
    return (
        await session.execute(
            select(User, *_profile_columns())
            .outerjoin(Profile, Profile.user_id == User.id)
            .where(User.id == user_id)
        )
    ).one_or_none()


async def standing_ban(session: AsyncSession, phone_hash: str) -> BannedIdentity | None:
    found: BannedIdentity | None = await session.scalar(
        select(BannedIdentity).where(
            BannedIdentity.kind == BanKind.PHONE_HASH,
            BannedIdentity.value == phone_hash,
            BannedIdentity.lifted_at.is_(None),
        )
    )
    return found


async def lift_ban(
    session: AsyncSession, phone_hash: str, *, by: UUID, reason: str, at: datetime
) -> int:
    """Lift the number's standing `ban` row in place (D-922): how many lifted,
    0 or 1. The database refuses any other change to the table."""
    lifted = await session.execute(
        update(BannedIdentity)
        .where(
            BannedIdentity.kind == BanKind.PHONE_HASH,
            BannedIdentity.value == phone_hash,
            BannedIdentity.reason == "ban",
            BannedIdentity.lifted_at.is_(None),
        )
        .values(lifted_at=at, lifted_by=by, lift_reason=reason)
        .execution_options(synchronize_session=False)
    )
    return int(lifted.rowcount)  # type: ignore[attr-defined]


async def balance_of(session: AsyncSession, user_id: UUID) -> int:
    balance = await session.scalar(
        select(Wallet.balance).where(Wallet.user_id == user_id)
    )
    return int(balance or 0)


async def photos_of(
    session: AsyncSession, user_id: UUID, kinds: Iterable[PhotoKind], limit: int
) -> Sequence[Photo]:
    """A person's photos of `kinds`, any status, newest first."""
    rows = await session.scalars(
        select(Photo)
        .where(Photo.user_id == user_id, Photo.kind.in_(list(kinds)))
        .order_by(Photo.created_at.desc(), Photo.id.desc())
        .limit(limit)
    )
    return rows.all()


async def pending_photos(
    session: AsyncSession,
    kinds: Iterable[PhotoKind],
    *,
    after: _Key | None,
    limit: int,
) -> Sequence[Photo]:
    """The moderation queue: pending photos of `kinds`, oldest first."""
    query = (
        select(Photo)
        .where(Photo.status == ReviewStatus.PENDING, Photo.kind.in_(list(kinds)))
        .order_by(Photo.created_at, Photo.id)
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(Photo.created_at, Photo.id) > after)
    return (await session.scalars(query)).all()


async def photo(session: AsyncSession, photo_id: UUID) -> Photo | None:
    found: Photo | None = await session.get(Photo, photo_id)
    return found


async def fraud_of(
    session: AsyncSession, user_id: UUID, limit: int
) -> tuple[FraudScore | None, Sequence[FraudEvent]]:
    score: FraudScore | None = await session.get(FraudScore, user_id)
    events = await session.scalars(
        select(FraudEvent)
        .where(FraudEvent.user_id == user_id)
        .order_by(FraudEvent.created_at.desc(), FraudEvent.id.desc())
        .limit(limit)
    )
    return score, events.all()


def _reports() -> Select[Any]:
    """A report with its two people's names and statuses."""
    reporter, reporter_profile = aliased(User), aliased(Profile)
    reported, reported_profile = aliased(User), aliased(Profile)
    return (
        select(
            Report,
            reporter.status.label("reporter_status"),
            reporter_profile.first_name.label("reporter_first_name"),
            reporter_profile.username.label("reporter_username"),
            reported.status.label("reported_status"),
            reported_profile.first_name.label("reported_first_name"),
            reported_profile.username.label("reported_username"),
        )
        .join(reporter, reporter.id == Report.reporter_id)
        .outerjoin(reporter_profile, reporter_profile.user_id == Report.reporter_id)
        .join(reported, reported.id == Report.reported_id)
        .outerjoin(reported_profile, reported_profile.user_id == Report.reported_id)
    )


async def reports_page(
    session: AsyncSession, status: ReportStatus, *, after: _Key | None, limit: int
) -> Sequence[Row[Any]]:
    """Reports in `status`, oldest first by `(created_at, id)`: a queue."""
    query = (
        _reports()
        .where(Report.status == status)
        .order_by(Report.created_at, Report.id)
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(Report.created_at, Report.id) > after)
    return (await session.execute(query)).all()


async def reports_of(
    session: AsyncSession,
    *,
    about: UUID | None = None,
    by: UUID | None = None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Reports about someone, or by someone, newest first."""
    query = _reports().order_by(Report.created_at.desc(), Report.id.desc()).limit(limit)
    if about is not None:
        query = query.where(Report.reported_id == about)
    if by is not None:
        query = query.where(Report.reporter_id == by)
    return (await session.execute(query)).all()


async def report_row(session: AsyncSession, report_id: UUID) -> Row[Any] | None:
    return (
        await session.execute(_reports().where(Report.id == report_id))
    ).one_or_none()


async def report_for_update(session: AsyncSession, report_id: UUID) -> Report | None:
    found: Report | None = await session.scalar(
        select(Report)
        .where(Report.id == report_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return found


async def ledger_of(
    session: AsyncSession, user_id: UUID, limit: int
) -> Sequence[LedgerEntry]:
    rows = await session.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
    )
    return rows.all()


async def threads_of(
    session: AsyncSession, user_id: UUID, limit: int
) -> Sequence[Row[Any]]:
    """A person's Threads, the newest first, each with the other person."""
    other_id = case(
        (Thread.user_low == user_id, Thread.user_high), else_=Thread.user_low
    )
    other, other_profile = aliased(User), aliased(Profile)
    query = (
        select(
            Thread,
            other.id.label("other_id"),
            other.status.label("other_status"),
            other_profile.first_name.label("other_first_name"),
            other_profile.username.label("other_username"),
        )
        .join(other, other.id == other_id)
        .outerjoin(other_profile, other_profile.user_id == other.id)
        .where(or_(Thread.user_low == user_id, Thread.user_high == user_id))
        .order_by(Thread.created_at.desc(), Thread.id.desc())
        .limit(limit)
    )
    return (await session.execute(query)).all()


async def thread_exists(session: AsyncSession, thread_id: UUID) -> bool:
    found = await session.scalar(select(Thread.id).where(Thread.id == thread_id))
    return found is not None


async def messages_page(
    session: AsyncSession, thread_id: UUID, *, after: _Key | None, limit: int
) -> Sequence[Message]:
    """**Every** message of the Thread, oldest first, by `thread_id` alone:
    never through a `thread_clears.cleared_at`, which is one person's view
    (T-7.8, D-006), so what either cleared is here, as a report's evidence is
    (`safety.repository.thread_messages`)."""
    query = (
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at, Message.id)
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(Message.created_at, Message.id) > after)
    return (await session.scalars(query)).all()


async def audit_page(
    session: AsyncSession, *, action: str | None, after: _Key | None, limit: int
) -> Sequence[AuditLogEntry]:
    query = (
        select(AuditLogEntry)
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        .limit(limit)
    )
    if action is not None:
        query = query.where(AuditLogEntry.action == action)
    if after is not None:
        query = query.where(tuple_(AuditLogEntry.created_at, AuditLogEntry.id) < after)
    return (await session.scalars(query)).all()


async def freezes_page(
    session: AsyncSession,
    freeze_actions: Sequence[str],
    *,
    after: _Key | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Accounts frozen now, each with the audit row that froze them last,
    newest freeze first. An account frozen with no such row (by hand, before
    T-9.5) sorts by when it was created."""
    last = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.target_type == "user",
            AuditLogEntry.target_id == User.id,
            AuditLogEntry.action.in_(list(freeze_actions)),
        )
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        .limit(1)
        .lateral("last_freeze")
    )
    sort_at = func.coalesce(last.c.created_at, User.created_at)
    query = (
        select(
            User,
            *_profile_columns(),
            sort_at.label("sort_at"),
            last.c.created_at.label("frozen_at"),
            last.c.actor_id.label("frozen_by"),
            last.c.meta.label("freeze_meta"),
        )
        .outerjoin(Profile, Profile.user_id == User.id)
        .outerjoin(last, true())
        .where(User.status == UserStatus.FROZEN)
        .order_by(sort_at.desc(), User.id.desc())
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(sort_at, User.id) < after)
    return (await session.execute(query)).all()


# --- The dashboard's counts (D-926) ------------------------------------------------------


async def users_by_status(session: AsyncSession) -> dict[UserStatus, int]:
    rows = await session.execute(
        select(User.status, func.count())
        .where(User.id != SYSTEM_USER_ID)
        .group_by(User.status)
    )
    return {status: int(count) for status, count in rows.all()}


async def signups_since(session: AsyncSession, since: datetime) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.id != SYSTEM_USER_ID, User.created_at >= since)
    )
    return int(count or 0)


async def open_reports(session: AsyncSession) -> tuple[int, datetime | None]:
    row = (
        await session.execute(
            select(func.count(), func.min(Report.created_at)).where(
                Report.status == ReportStatus.OPEN
            )
        )
    ).one()
    return int(row[0]), row[1]


async def pending_count(session: AsyncSession, kinds: Iterable[PhotoKind]) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Photo)
        .where(Photo.status == ReviewStatus.PENDING, Photo.kind.in_(list(kinds)))
    )
    return int(count or 0)


async def open_claims(session: AsyncSession) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(RefundRequest)
        .where(RefundRequest.status == "open")
    )
    return int(count or 0)
