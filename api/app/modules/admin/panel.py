"""The moderation panel's rules (T-9.5, D-920 to D-929): what staff read and do.

**Every call writes `audit_log`**, a read included, inside the transaction that
read or changed what it names (02-ARCHITECTURE §12); a refused call changes
nothing and writes nothing. Staff are moderators and admins; what only an
admin may do is refused here as `FORBIDDEN`, beside the route's own
`require_role` (P-30: the web's gate is never protection).

Its own module, beside `service.py`: `admin.service` (the audit trail and
`app_config`) is imported by scoring, payments and safety, and this imports
them, so the two can't be one file without a cycle.

- **Status (D-922):** a moderator may freeze; ban, unban and unfreeze are an
  admin's. A freeze or a ban revokes every session and closes every socket in
  its transaction (D-557). A ban keeps the number in `banned_identities`; an
  erased account, whose row can't leave `deleted`, is banned by its number
  alone (D-500). An unban lifts that row in place, never deletes it, and the
  account returns to `deleted` if it had asked to go before the ban, so the
  erasure runs as /privacy promises; else `active`. An unfreeze is the
  founder's tool's own path (`safety.scoring.unfreeze`, D-906), which starts
  the score again. A ban stops an erasure and keeps the data (P-401, D-929).
- **Velas (D-923):** an admin grants (`admin_grant`) or corrects
  (`admin_correction`) up to 1,000 at once, a man's only (D-076), each naming
  its call's audit row, under an `Idempotency-Key`: the same key again changes
  nothing. A correction beyond the balance is `NOT_ALLOWED`, never
  `INSUFFICIENT_CREDITS`, which the web reads as the man's own.
- **Reports (D-921):** `none` dismisses; `warn` (recorded only), `freeze` and
  `ban` action, the last two as status changes, `ban` an admin's.
- **Photos (D-925):** public and private only, never a selfie or the face
  photo; staff approve a pending one or take down a pending or approved one.
- **A Thread's messages (D-924):** every one, what either person cleared
  included (T-7.8, D-006), each read audited with the reason given.
- **What a moderator sees (D-926, D-927):** counts, never revenue; a number
  masked, never whole.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
from app.core.enums import (
    FraudBand,
    Gender,
    LedgerReason,
    MessageKind,
    ReportStatus,
    ReviewStatus,
    Role,
    UserStatus,
)
from app.core.errors import AppError, invalid_field
from app.core.pagination import Cursor, PageParams
from app.core.providers.storage import StorageProvider
from app.core.queue import Queue
from app.core.security import decrypt_phone, hash_phone, normalize_phone
from app.core.storage_keys import public_url
from app.modules.admin import repository, rules, schemas
from app.modules.admin.rules import ReportAction, StatusTarget
from app.modules.admin.service import SYSTEM_USER_ID, audit
from app.modules.auth import service as auth_service
from app.modules.discovery.rules import like_prefix
from app.modules.payments import rules as payments_rules
from app.modules.payments import service as payments_service
from app.modules.photos import moderation as moderation_rules
from app.modules.photos import service as photos_service
from app.modules.photos.models import Photo
from app.modules.safety import scoring
from app.modules.safety.models import FraudEvent, FraudScore, Report
from app.modules.users import repository as users_repository
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType

# Every list here is keyed `(created_at, id)`, or its freeze's time and id.
KEY: Final[Cursor[tuple[datetime, UUID]]] = Cursor(tuple[AwareDatetime, UUID])

# The audit actions this module writes. The status changes name what they did.
FREEZE: Final = "user.freeze"
BAN: Final = "user.ban"
UNBAN: Final = "user.unban"
# What froze an account, for the freezes list: T-9.2's automatic one and staff's.
FREEZE_ACTIONS: Final = (scoring.FREEZE, FREEZE)

# What a number typed into search looks like: digits and what people put
# between them. Anything else is a name, a username or an id.
_PHONE_LIKE = re.compile(r"\+?[\d\s()-]{10,20}")
SEARCH_MIN, SEARCH_MAX = 2, 50


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def _forbidden() -> AppError:
    return AppError("FORBIDDEN", "You don't have access to this.", status=403)


def _refused(why: str, message: str, **details: Any) -> AppError:
    return AppError("NOT_ALLOWED", message, status=422, details={"why": why, **details})


def _after(params: PageParams) -> tuple[datetime, UUID] | None:
    return KEY.decode(params.cursor) if params.cursor is not None else None


def _age(user: User) -> int | None:
    return (
        None if user.dob is None else users_service.age_on(user.dob, clock.today_ist())
    )


def _user_out(row: Row[Any]) -> schemas.AdminUser:
    user: User = row[0]
    return schemas.AdminUser(
        id=user.id,
        first_name=row.first_name,
        username=row.username,
        city=row.city,
        gender=user.gender,
        age=_age(user),
        role=user.role,
        status=user.status,
        onboarding_step=user.onboarding_step,
        erased=user.anonymised_at is not None,
        deleted_requested_at=user.deleted_requested_at,
        last_active_at=user.last_active_at,
        created_at=user.created_at,
    )


# --- The dashboard (D-926) ---------------------------------------------------------------


async def metrics(session: AsyncSession, staff: User) -> schemas.AdminMetrics:
    now = clock.now()
    async with session.begin():
        by_status = await repository.users_by_status(session)
        reports_open, oldest = await repository.open_reports(session)
        revenue = None
        if staff.role is Role.ADMIN:
            year = payments_rules.financial_year_of(now)
            revenue = schemas.AdminRevenue(
                last_7_days_paise=await payments_service.paid_between(
                    session, now - timedelta(days=7), now
                ),
                last_30_days_paise=await payments_service.paid_between(
                    session, now - timedelta(days=30), now
                ),
                financial_year=year.label,
                financial_year_paise=await payments_service.paid_between(
                    session, year.starts_at, year.ends_at
                ),
            )
        figures = schemas.AdminMetrics(
            users_by_status={status: by_status.get(status, 0) for status in UserStatus},
            signups_24h=await repository.signups_since(
                session, now - timedelta(days=1)
            ),
            signups_7d=await repository.signups_since(session, now - timedelta(days=7)),
            reports_open=reports_open,
            oldest_open_report_at=oldest,
            photos_pending=await repository.pending_count(
                session, rules.PANEL_PHOTO_KINDS
            ),
            frozen=by_status.get(UserStatus.FROZEN, 0),
            claims_open=await repository.open_claims(session),
            revenue=revenue,
        )
        await audit(session, staff.id, "metrics.read", {"revenue": revenue is not None})
    return figures


# --- People ---------------------------------------------------------------------------


def _search(q: str | None, settings: Settings) -> tuple[str, dict[str, Any]]:
    """What `q` asks for: nothing (the newest), a whole number, matched by its
    hash only, never a part of one (D-061), an account's id, or the start of
    a username or first name."""
    term = (q or "").strip()
    if not term:
        return "newest", {}
    try:
        return "id", {"user_id": UUID(term)}
    except ValueError:
        pass
    if _PHONE_LIKE.fullmatch(term):
        try:
            phone = normalize_phone(term)
        except AppError:
            raise invalid_field("q", "isn't a whole Indian mobile number") from None
        return "phone", {"phone_hash": hash_phone(phone, settings)}
    name = term.removeprefix("@")
    if not SEARCH_MIN <= len(name) <= SEARCH_MAX:
        raise invalid_field(
            "q", f"must be {SEARCH_MIN} to {SEARCH_MAX} characters, a number or an id"
        )
    return "name", {"prefix": like_prefix(name)}


async def users(
    session: AsyncSession,
    staff: User,
    q: str | None,
    params: PageParams,
    settings: Settings,
) -> schemas.AdminUserPage:
    """`GET /admin/users`. The audit row says how staff searched, never what
    they typed: a number is never written down (rule 15)."""
    by, where = _search(q, settings)
    after = _after(params)
    async with session.begin():
        rows = await repository.users_page(
            session, **where, after=after, limit=params.fetch
        )
        await audit(session, staff.id, "users.search", {"by": by})
    return schemas.AdminUserPage.of(
        [_user_out(row) for row in rows],
        params,
        lambda user: KEY.encode((user.created_at, user.id)),
    )


async def _photo_out(
    photo: Photo, storage: StorageProvider, settings: Settings
) -> schemas.AdminPhoto:
    """A photo with where staff view it: an approved public one at the CDN, an
    approved private one by its scored copy (D-700), any other by a 10-minute
    link to the private copy; none for a possible minor's, whose every copy
    is gone (D-093)."""
    url: str | None = None
    if photo.status is ReviewStatus.APPROVED and photo.public_key:
        url = public_url(settings, photo.public_key)
    elif photo.status is ReviewStatus.APPROVED and photo.scored_key:
        url = await storage.presign_get(settings.R2_BUCKET_PRIVATE, photo.scored_key)
    elif photo.reject_reason != moderation_rules.MINOR_SUSPECTED:
        url = await storage.presign_get(settings.R2_BUCKET_PRIVATE, photo.raw_key)
    minor = (photo.moderation or {}).get("minor")
    return schemas.AdminPhoto(
        id=photo.id,
        user_id=photo.user_id,
        kind=photo.kind,
        position=photo.position,
        status=photo.status,
        reject_reason=photo.reject_reason,
        minor_score=float(minor) if isinstance(minor, int | float) else None,
        url=url,
        created_at=photo.created_at,
    )


def _ref(
    user_id: UUID, status: UserStatus, first_name: str | None, username: str | None
) -> schemas.AdminUserRef:
    return schemas.AdminUserRef(
        id=user_id, first_name=first_name, username=username, status=status
    )


def _report_out(row: Row[Any]) -> schemas.AdminReport:
    report: Report = row[0]
    return schemas.AdminReport(
        id=report.id,
        reporter=_ref(
            report.reporter_id,
            row.reporter_status,
            row.reporter_first_name,
            row.reporter_username,
        ),
        reported=_ref(
            report.reported_id,
            row.reported_status,
            row.reported_first_name,
            row.reported_username,
        ),
        reason=report.reason,
        details=report.details,
        thread_id=report.thread_id,
        status=report.status,
        action=ReportAction(report.action) if report.action is not None else None,
        resolved_by=report.resolved_by,
        resolved_at=report.resolved_at,
        created_at=report.created_at,
        due_at=report.created_at + rules.REPORT_SLA,
    )


def _fraud_out(
    score: FraudScore | None, events: Sequence[FraudEvent]
) -> schemas.AdminFraud | None:
    """The score and its newest events, or None if nothing was ever signalled.
    Events with no score yet read as 0 and normal, as the next sweep starts."""
    if score is None and not events:
        return None
    return schemas.AdminFraud(
        score=score.score if score is not None else 0,
        band=score.band if score is not None else FraudBand.NORMAL,
        signals=score.signals if score is not None else None,
        counted_from=score.counted_from if score is not None else None,
        events=[
            schemas.AdminFraudEvent(
                signal=event.signal,
                weight=event.weight,
                meta=event.meta,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


async def user_detail(
    session: AsyncSession,
    staff: User,
    user_id: UUID,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> schemas.AdminUserDetail:
    """`GET /admin/users/{id}`: the account and the newest 50 of each list.
    An admin sees the whole number, and the audit row says so; a moderator a
    masked one (D-927)."""
    async with session.begin():
        row = await repository.user_row(session, user_id)
        if row is None:
            raise _not_found()
        user: User = row[0]
        ban = await repository.standing_ban(session, user.phone_hash)
        photos = await repository.photos_of(
            session, user_id, rules.PANEL_PHOTO_KINDS, rules.DETAIL_LIMIT
        )
        score, events = await repository.fraud_of(session, user_id, rules.DETAIL_LIMIT)
        about = await repository.reports_of(
            session, about=user_id, limit=rules.DETAIL_LIMIT
        )
        by = await repository.reports_of(session, by=user_id, limit=rules.DETAIL_LIMIT)
        ledger = await repository.ledger_of(session, user_id, rules.DETAIL_LIMIT)
        threads = await repository.threads_of(session, user_id, rules.DETAIL_LIMIT)
        balance = await repository.balance_of(session, user_id)
        phone: str | None = None
        if user.phone_enc is not None:
            whole = decrypt_phone(user.phone_enc, settings)
            phone = whole if staff.role is Role.ADMIN else rules.masked(whole)
        shown = phone is not None and staff.role is Role.ADMIN
        await audit(
            session,
            staff.id,
            "user.read",
            {"phone_shown": shown},
            target=("user", user_id),
        )
    return schemas.AdminUserDetail(
        user=_user_out(row),
        phone=phone,
        phone_masked=phone is not None and not shown,
        is_verified=user.is_verified,
        balance=balance,
        ban=(
            schemas.AdminBan(reason=ban.reason, created_at=ban.created_at)
            if ban is not None
            else None
        ),
        photos=[await _photo_out(photo, storage, settings) for photo in photos],
        fraud=_fraud_out(score, events),
        reports_about=[_report_out(report) for report in about],
        reports_by=[_report_out(report) for report in by],
        ledger=[
            schemas.AdminLedgerEntry(
                id=entry.id,
                delta=entry.delta,
                balance_after=entry.balance_after,
                reason=entry.reason,
                ref_type=entry.ref_type,
                ref_id=entry.ref_id,
                created_at=entry.created_at,
            )
            for entry in ledger
        ],
        threads=[
            schemas.AdminThread(
                id=thread_row[0].id,
                other=_ref(
                    thread_row.other_id,
                    thread_row.other_status,
                    thread_row.other_first_name,
                    thread_row.other_username,
                ),
                status=thread_row[0].status,
                origin=thread_row[0].origin,
                message_count=thread_row[0].message_count,
                last_message_at=thread_row[0].last_message_at,
                created_at=thread_row[0].created_at,
            )
            for thread_row in threads
        ],
    )


# --- Status (D-922) ---------------------------------------------------------------------


async def _locked(session: AsyncSession, user_id: UUID) -> User:
    if user_id == SYSTEM_USER_ID:
        raise _not_found()
    try:
        return await users_service.locked_user(session, user_id)
    except LookupError:
        raise _not_found() from None


async def _freeze(
    session: AsyncSession, staff: User, user: User, reason: str, *, report: UUID | None
) -> bool:
    """Freeze `user` as staff, if they can sign in (D-902). True if frozen
    now; False if already frozen or banned, which a report leaves as it is."""
    if user.status in (UserStatus.FROZEN, UserStatus.BANNED) and report is not None:
        return False
    if user.status is UserStatus.FROZEN:
        raise _refused("already_frozen", "This account is frozen already.")
    if user.status not in rules.FREEZABLE:
        raise _refused(user.status.value, "Only an account that can sign in is frozen.")
    before = user.status
    user.status = UserStatus.FROZEN
    await auth_service.sign_out_everywhere(session, user.id)
    await audit(
        session,
        staff.id,
        FREEZE,
        {"reason": reason, "from": before.value, "report_id": _str(report)},
        target=("user", user.id),
    )
    return True


async def _ban(
    session: AsyncSession, staff: User, user: User, reason: str, *, report: UUID | None
) -> bool:
    """Ban `user` and their number (D-922). True if banned now; False if
    already banned, which a report leaves as it is."""
    if staff.role is not Role.ADMIN:
        raise _forbidden()
    erased = user.anonymised_at is not None
    if erased:
        if await repository.standing_ban(session, user.phone_hash) is not None:
            if report is not None:
                return False
            raise _refused("already_banned", "This number is banned already.")
    elif user.status is UserStatus.BANNED:
        if report is not None:
            return False
        raise _refused("already_banned", "This account is banned already.")
    elif user.status not in rules.BANNABLE:
        raise _refused(user.status.value, "This account can't be banned.")
    before = user.status
    if not erased:
        user.status = UserStatus.BANNED
        await auth_service.sign_out_everywhere(session, user.id)
    await users_repository.ban_phone_hash(session, user.phone_hash, rules.BAN_REASON)
    await audit(
        session,
        staff.id,
        BAN,
        {
            "reason": reason,
            "from": before.value,
            "erased": erased,
            "report_id": _str(report),
        },
        target=("user", user.id),
    )
    return True


async def _unban(session: AsyncSession, staff: User, user: User, reason: str) -> None:
    """Lift the number's ban in place (D-922) and give the account back: to
    `deleted` if it had asked to go before the ban, so the erasure runs, else
    `active`. An erased account's number is lifted alone."""
    erased = user.anonymised_at is not None
    if not erased and user.status is not UserStatus.BANNED:
        raise _refused("not_banned", "This account isn't banned.")
    lifted = await repository.lift_ban(
        session, user.phone_hash, by=staff.id, reason=reason, at=clock.now()
    )
    if erased and not lifted:
        raise _refused("not_banned", "This number isn't banned.")
    to = user.status
    if not erased:
        to = (
            UserStatus.DELETED
            if user.deleted_requested_at is not None
            else UserStatus.ACTIVE
        )
        user.status = to
    await audit(
        session,
        staff.id,
        UNBAN,
        {"reason": reason, "to": to.value, "lifted": lifted, "erased": erased},
        target=("user", user.id),
    )


async def _unfreeze(
    session: AsyncSession, staff: User, user: User, reason: str
) -> None:
    """The founder's tool's own path (D-906): active, the score started again
    from now, audited as `fraud.unfreeze`."""
    if user.status is not UserStatus.FROZEN:
        raise _refused("not_frozen", "This account isn't frozen.")
    try:
        await scoring.unfreeze(session, user.id, by=staff.id, reason=reason)
    except scoring.NotAnAdmin:
        raise _forbidden() from None


def _str(value: UUID | None) -> str | None:
    return None if value is None else str(value)


async def set_status(
    session: AsyncSession,
    staff: User,
    user_id: UUID,
    target: StatusTarget,
    reason: str,
) -> None:
    """`POST /admin/users/{id}/status`: freeze, ban, or lift either (D-922)."""
    if not rules.may(staff.role, target):
        raise _forbidden()
    async with session.begin():
        user = await _locked(session, user_id)
        if target is StatusTarget.FROZEN:
            await _freeze(session, staff, user, reason, report=None)
        elif target is StatusTarget.BANNED:
            await _ban(session, staff, user, reason, report=None)
        elif user.status is UserStatus.FROZEN:
            await _unfreeze(session, staff, user, reason)
        else:
            await _unban(session, staff, user, reason)


# --- Velas (D-923) ----------------------------------------------------------------------

CREDITS: Final = "user.credits"


async def _correct(
    session: AsyncSession, user_id: UUID, amount: int, ref: Ref, key: str
) -> None:
    """The one place an admin's correction is debited: named in the wallet's
    `DEBIT_CALLERS` (P-152, D-651). The balance was checked under the lock."""
    await wallet_service.debit(
        session, user_id, amount, LedgerReason.ADMIN_CORRECTION, ref=ref, event=key
    )


async def change_credits(
    session: AsyncSession,
    staff: User,
    user_id: UUID,
    delta: int,
    reason: str,
    key: str,
) -> None:
    """`POST /admin/users/{id}/credits`: an admin's grant or correction, a
    man's only (D-076), under `key`. The same key again, for the same change,
    changes nothing and writes nothing; for another, `ALREADY_EXISTS`."""
    if staff.role is not Role.ADMIN:
        raise _forbidden()
    if delta == 0:
        raise invalid_field("delta", "must not be 0")
    ledger_reason = (
        LedgerReason.ADMIN_GRANT if delta > 0 else LedgerReason.ADMIN_CORRECTION
    )
    async with session.begin():
        row = await repository.user_row(session, user_id)
        if row is None:
            raise _not_found()
        if row[0].gender is not Gender.MALE:
            raise _refused("not_a_man", "Only a man's account holds Velas.")
        await wallet_service.lock_wallets(session, [user_id])
        for earlier_reason in (LedgerReason.ADMIN_GRANT, LedgerReason.ADMIN_CORRECTION):
            earlier = await wallet_service.entry_for(
                session, user_id, earlier_reason, key
            )
            if earlier is None:
                continue
            if earlier_reason is ledger_reason and earlier.delta == delta:
                return
            raise AppError(
                "ALREADY_EXISTS",
                "That key was used for another change.",
                status=409,
            )
        balance = await repository.balance_of(session, user_id)
        if delta < 0 and balance < -delta:
            raise _refused(
                "balance", "That's more than this account holds.", balance=balance
            )
        audit_id = await audit(
            session,
            staff.id,
            CREDITS,
            {"delta": delta, "reason": reason},
            target=("user", user_id),
        )
        ref = Ref(RefType.AUDIT_LOG, audit_id)
        if delta > 0:
            await wallet_service.credit(
                session, user_id, delta, LedgerReason.ADMIN_GRANT, ref=ref, event=key
            )
        else:
            await _correct(session, user_id, -delta, ref, key)


# --- Reports (D-921) --------------------------------------------------------------------


async def reports(
    session: AsyncSession, staff: User, status: ReportStatus, params: PageParams
) -> schemas.AdminReportPage:
    after = _after(params)
    async with session.begin():
        rows = await repository.reports_page(
            session, status, after=after, limit=params.fetch
        )
        await audit(session, staff.id, "reports.list", {"status": status.value})
    return schemas.AdminReportPage.of(
        [_report_out(row) for row in rows],
        params,
        lambda report: KEY.encode((report.created_at, report.id)),
    )


async def resolve_report(
    session: AsyncSession,
    staff: User,
    report_id: UUID,
    action: ReportAction,
    note: str,
) -> None:
    """Close a report with what was done. `freeze` and `ban` change the
    reported person's status as `set_status` would, but someone frozen or
    banned already is left as they are; a moderator never bans."""
    if action is ReportAction.BAN and staff.role is not Role.ADMIN:
        raise _forbidden()
    async with session.begin():
        report = await repository.report_for_update(session, report_id)
        if report is None:
            raise _not_found()
        if report.status is not ReportStatus.OPEN:
            raise _refused("resolved", "This report was resolved already.")
        changed = False
        if action in (ReportAction.FREEZE, ReportAction.BAN):
            user = await _locked(session, report.reported_id)
            act = _freeze if action is ReportAction.FREEZE else _ban
            changed = await act(session, staff, user, note, report=report.id)
        report.status = rules.REPORT_STATUS[action]
        report.action = action.value
        report.resolved_by = staff.id
        report.resolved_at = clock.now()
        await audit(
            session,
            staff.id,
            "report.resolve",
            {"action": action.value, "note": note, "status_changed": changed},
            target=("report", report.id),
        )


# --- Photos (D-925) ---------------------------------------------------------------------


async def moderation(
    session: AsyncSession,
    staff: User,
    params: PageParams,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> schemas.AdminPhotoPage:
    after = _after(params)
    async with session.begin():
        photos = await repository.pending_photos(
            session, rules.PANEL_PHOTO_KINDS, after=after, limit=params.fetch
        )
        await audit(session, staff.id, "moderation.list")
    return schemas.AdminPhotoPage.of(
        [await _photo_out(photo, storage, settings) for photo in photos],
        params,
        lambda photo: KEY.encode((photo.created_at, photo.id)),
    )


async def decide_photo(
    session: AsyncSession,
    staff: User,
    photo_id: UUID,
    approve: bool,
    reason: str | None,
    note: str | None,
    *,
    storage: StorageProvider,
    settings: Settings,
    queue: Queue,
) -> None:
    """Approve a pending photo, or take down a pending or approved one, with
    a reason and a note; an approval takes neither."""
    if approve and (reason is not None or note is not None):
        raise invalid_field("reason", "is only for a rejection")
    if not approve and (reason is None or note is None):
        raise invalid_field("reason", "and a note are required to reject")
    async with session.begin():
        decided = await photos_service.decide_by_staff(
            session,
            photo_id,
            approve=approve,
            reason=reason,
            by=staff.id,
            storage=storage,
            settings=settings,
        )
        await audit(
            session,
            staff.id,
            "photo.decide",
            {"approve": approve, "reason": reason, "note": note},
            target=("photo", photo_id),
        )
    await photos_service.after_staff_decision(
        decided, storage=storage, settings=settings, queue=queue
    )


# --- A Thread's messages (D-924) --------------------------------------------------------


async def thread_messages(
    session: AsyncSession,
    staff: User,
    thread_id: UUID,
    reason: str,
    params: PageParams,
    *,
    storage: StorageProvider,
    settings: Settings,
) -> schemas.AdminMessagePage:
    """Every message, oldest first, each page's read audited with its reason,
    which is at least 10 characters once its spaces are trimmed."""
    reason = reason.strip()
    if len(reason) < rules.REASON_MIN:
        raise invalid_field(
            "reason", f"must say why, in {rules.REASON_MIN} characters or more"
        )
    after = _after(params)
    async with session.begin():
        if not await repository.thread_exists(session, thread_id):
            raise _not_found()
        messages = await repository.messages_page(
            session, thread_id, after=after, limit=params.fetch
        )
        await audit(
            session,
            staff.id,
            "thread.read",
            {"reason": reason},
            target=("thread", thread_id),
        )
    items = [
        schemas.AdminMessage(
            id=message.id,
            sender_id=message.sender_id,
            kind=message.kind,
            body=message.body_raw if message.body_raw is not None else message.body,
            masked=message.masked,
            duration_s=message.duration_s,
            audio_url=(
                await storage.presign_get(settings.R2_BUCKET_PRIVATE, message.media_key)
                if message.kind is MessageKind.VOICE and message.media_key
                else None
            ),
            created_at=message.created_at,
        )
        for message in messages
    ]
    return schemas.AdminMessagePage.of(
        items, params, lambda message: KEY.encode((message.created_at, message.id))
    )


# --- The record -------------------------------------------------------------------------


async def audit_entries(
    session: AsyncSession, staff: User, action: str | None, params: PageParams
) -> schemas.AuditEntryPage:
    after = _after(params)
    async with session.begin():
        rows = await repository.audit_page(
            session, action=action, after=after, limit=params.fetch
        )
        await audit(session, staff.id, "audit.read", {"action": action})
    return schemas.AuditEntryPage.of(
        [
            schemas.AuditEntry(
                id=row.id,
                actor_id=row.actor_id,
                actor_is_system=row.actor_id == SYSTEM_USER_ID,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                meta=row.meta,
                created_at=row.created_at,
            )
            for row in rows
        ],
        params,
        lambda entry: KEY.encode((entry.created_at, entry.id)),
    )


async def freezes(
    session: AsyncSession, staff: User, params: PageParams
) -> schemas.AdminFreezePage:
    """Accounts frozen now, the newest freeze first (P-800, D-928)."""
    after = _after(params)
    async with session.begin():
        rows = await repository.freezes_page(
            session, FREEZE_ACTIONS, after=after, limit=params.fetch
        )
        await audit(session, staff.id, "freezes.list")
    sorted_at = {row[0].id: row.sort_at for row in rows}
    items: list[schemas.AdminFreeze] = []
    for row in rows:
        automatic = row.frozen_by == SYSTEM_USER_ID
        meta = row.freeze_meta or {}
        items.append(
            schemas.AdminFreeze(
                user=_user_out(row),
                frozen_at=row.frozen_at,
                automatic=automatic,
                rule=meta.get("rule") if automatic else None,
                score=meta.get("score") if automatic else None,
            )
        )
    return schemas.AdminFreezePage.of(
        items,
        params,
        lambda freeze: KEY.encode((sorted_at[freeze.user.id], freeze.user.id)),
    )
