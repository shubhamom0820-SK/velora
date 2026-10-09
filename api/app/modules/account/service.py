"""Settings and data rights (T-9.6): the privacy switches, pausing, deleting an
account and exporting one's own data; and the worker's halves, writing an
export, expiring it, and erasing deleted accounts.

- **Deleting** (D-500): the account is `deleted` at once, hidden everywhere
  that shows only `active` accounts, every session revoked. Signing in again
  before the erasure restores it (`users.service.restore_if_deleted`).
- **Erasing** (D-500, D-503): a daily job at 03:30 IST erases every account
  deleted at least 29 days ago, so each is erased within the 30 days `/privacy`
  promises. `erasure.py` says what goes and what stays (D-051).
- **Exporting** (D-502): JSON of the user's own data, written by the worker to
  the private bucket, served by a link signed until 24 hours after it was ready,
  and deleted then. Nothing in it is another person's.

Logs name users and exports by id, never a number, a key or a link (rule 15).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock
from app.core.config import APP_NAME, Settings
from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.providers.storage import ObjectNotFound, StorageProvider
from app.core.queue import EXPIRE_EXPORT, EXPORT_DATA, Queue
from app.core.security import decrypt_phone
from app.core.storage_keys import export_key
from app.modules.account import repository
from app.modules.account.models import DataExport
from app.modules.account.schemas import DataExport as DataExportOut
from app.modules.account.schemas import DeletionScheduled, SettingsPatch
from app.modules.auth import service as auth_service
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import Me

log = structlog.get_logger(__name__)

# D-500: the daily job erases accounts deleted at least this long ago, so, run
# once a day, it erases each between day 29 and day 30: within the 30 days
# `/privacy` promises, which is `ERASE_BY`.
ERASE_AFTER = timedelta(days=29)
ERASE_BY = timedelta(days=30)
# D-502: an export's link, and its file, last this long after it is ready.
EXPORT_LINK = timedelta(hours=24)
# An export still pending this long after it was asked for is stuck (its job
# never ran, or failed past its tries): asking again makes a new one, and the
# daily job deletes any file it left.
STUCK_EXPORT = timedelta(hours=1)
EXPORT_VERSION = 1


# --- Settings and pause ------------------------------------------------------------


async def update_settings(
    session: AsyncSession, user: User, patch: SettingsPatch
) -> Me:
    """`PATCH /me/settings`: each switch sent, set; the rest left alone."""
    async with session.begin():
        profile = await repository.profile_for_update(session, user.id)
        for field in patch.model_fields_set:
            value = getattr(patch, field)
            if value is not None:
                setattr(profile, field, value)
        await session.flush()
        return await users_service.me(session, user)


async def pause(session: AsyncSession, user: User) -> None:
    """`POST /me/pause`: hidden from everyone, and no notifications (T-9.4),
    until resumed. Twice is once."""
    async with session.begin():
        locked = await users_service.locked_user(session, user.id)
        if locked.status is UserStatus.ACTIVE:
            locked.status = UserStatus.PAUSED


async def resume(session: AsyncSession, user: User) -> None:
    """`DELETE /me/pause`: back to active. Twice is once."""
    async with session.begin():
        locked = await users_service.locked_user(session, user.id)
        if locked.status is UserStatus.PAUSED:
            locked.status = UserStatus.ACTIVE


# --- Deleting (D-500) ----------------------------------------------------------------


async def delete_account(session: AsyncSession, user: User) -> DeletionScheduled:
    """`DELETE /me`: the account is `deleted` now and erased within 30 days.

    Who may delete is who may sign in, checked again under the lock: a ban or a
    freeze that landed since the request was let in still stops it, so deleting
    is never a way around one (D-051). Every session is revoked and every push
    subscription dropped, so nothing reaches the person after this.
    """
    now = clock.now()
    async with session.begin():
        locked = await users_service.locked_user(session, user.id)
        users_service.refuse_who_may_not_sign_in(locked)
        locked.status = UserStatus.DELETED
        locked.deleted_requested_at = now
        await auth_service.sign_out_everywhere(session, locked.id)
        await repository.delete_push_subscriptions(session, locked.id)
    log.info("account.deleted", user_id=str(user.id))
    return DeletionScheduled(erase_by=now + ERASE_BY)


# --- Exporting (D-502): the API's half ------------------------------------------------


async def request_export(
    session: AsyncSession,
    user: User,
    *,
    queue: Queue,
    storage: StorageProvider,
    settings: Settings,
) -> DataExportOut:
    """`POST /me/export`: a new export, queued for the worker; or the one
    already being made, or ready and unexpired, rather than a second."""
    now = clock.now()
    async with session.begin():
        # Two requests at once take turns, so they can't make two exports.
        await users_service.locked_user(session, user.id)
        latest = await repository.latest_export(session, user.id)
        if latest is not None and _still_useful(latest, now):
            return await _out(latest, now, storage, settings)
        export = await repository.insert_export(session, user.id)
        out = await _out(export, now, storage, settings)
    # After the commit, so the worker never looks for a row it can't see yet.
    await queue.enqueue(
        EXPORT_DATA, job_id=f"{EXPORT_DATA}:{export.id}", export_id=str(export.id)
    )
    log.info("export.requested", export_id=str(export.id))
    return out


async def latest_export(
    session: AsyncSession, user: User, *, storage: StorageProvider, settings: Settings
) -> DataExportOut:
    """`GET /me/export`: the newest export, with its link while it is ready."""
    async with session.begin():
        latest = await repository.latest_export(session, user.id)
    if latest is None:
        raise AppError(
            "NOT_FOUND", "You haven't asked for a copy of your data.", status=404
        )
    return await _out(latest, clock.now(), storage, settings)


def _still_useful(export: DataExport, now: datetime) -> bool:
    if export.status == "pending":
        return now - export.created_at < STUCK_EXPORT
    return export.status == "ready" and _unexpired(export, now)


def _unexpired(export: DataExport, now: datetime) -> bool:
    return export.expires_at is not None and export.expires_at > now


async def _out(
    export: DataExport, now: datetime, storage: StorageProvider, settings: Settings
) -> DataExportOut:
    """The export as the web sees it. A ready one past its expiry is expired
    already, whether or not its file's deletion has run; the link is signed
    only until `expires_at`, never past it."""
    status = export.status
    url = None
    if status == "ready" and not _unexpired(export, now):
        status = "expired"
    if status == "ready" and export.file_key and export.expires_at is not None:
        ttl = max(1, int((export.expires_at - now).total_seconds()))
        url = await storage.presign_get(
            settings.R2_BUCKET_PRIVATE, export.file_key, ttl
        )
    return DataExportOut(
        id=export.id,
        status=status,
        requested_at=export.created_at,
        expires_at=export.expires_at,
        url=url,
    )


# --- Exporting (D-502): the worker's half --------------------------------------------


async def write_export(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    export_id: UUID,
    storage: StorageProvider,
    settings: Settings,
    queue: Queue,
) -> str:
    """Write the export's file and mark it ready, then queue its expiry.

    The key is recorded before the file is written, so a file never exists
    that no row points to: a failure after the write leaves a pending export
    with its key, whose file the daily job deletes once it is stuck.
    """
    key: str
    async with sessionmaker() as session, session.begin():
        export = await repository.export_for_update(session, export_id)
        if export is None or export.status != "pending":
            return "nothing to do"
        key = export_key(export.user_id, export.id)
        export.file_key = key
        user_id = export.user_id
    async with sessionmaker() as session, session.begin():
        user = await users_service.get_user(session, user_id)
        document = await export_document(session, user, storage, settings)
    body = json.dumps(document, ensure_ascii=False, indent=2).encode()
    await storage.put_bytes(settings.R2_BUCKET_PRIVATE, key, body, "application/json")
    now = clock.now()
    async with sessionmaker() as session, session.begin():
        export = await repository.export_for_update(session, export_id)
        if export is None or export.status != "pending":
            return "nothing to do"
        export.status = "ready"
        export.ready_at = now
        export.expires_at = now + EXPORT_LINK
    await queue.enqueue(
        EXPIRE_EXPORT,
        job_id=f"{EXPIRE_EXPORT}:{export_id}",
        defer_by=EXPORT_LINK,
        export_id=str(export_id),
    )
    log.info("export.ready", export_id=str(export_id), size=len(body))
    return "ready"


async def fail_export(
    sessionmaker: async_sessionmaker[AsyncSession], export_id: UUID
) -> None:
    """The export's last try failed: `failed`, so asking again makes a new
    one. A file it may have written is left to `expire_export`."""
    async with sessionmaker() as session, session.begin():
        export = await repository.export_for_update(session, export_id)
        if export is not None and export.status == "pending":
            export.status = "failed"
    log.error("export.failed", export_id=str(export_id))


async def expire_export(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    export_id: UUID,
    storage: StorageProvider,
    settings: Settings,
) -> str:
    """Delete an export's file once its link has expired, read back as gone,
    and say so on its row: a ready export becomes `expired`, a stuck pending
    one `failed`. Not yet due, nothing happens; a file that won't go raises,
    so the job is tried again and the daily job tries after that."""
    now = clock.now()
    async with sessionmaker() as session, session.begin():
        export = await repository.export_for_update(session, export_id)
        if export is None:
            return "nothing to do"
        due = (
            (export.status == "ready" and not _unexpired(export, now))
            or export.status in ("expired", "failed")
            or (export.status == "pending" and now - export.created_at >= STUCK_EXPORT)
        )
        if not due:
            return "not yet"
        if export.file_key is not None:
            await delete_and_read_back(
                storage, [(settings.R2_BUCKET_PRIVATE, export.file_key)]
            )
            export.file_key = None
        if export.status == "ready":
            export.status = "expired"
        elif export.status == "pending":
            export.status = "failed"
    log.info("export.expired", export_id=str(export_id))
    return "expired"


async def export_document(
    session: AsyncSession, user: User, storage: StorageProvider, settings: Settings
) -> dict[str, Any]:
    """Everything that is the user's own, and nothing that is anyone else's.

    Other people appear in none of it: no id, name, username, number, location
    or words of theirs. Threads are numbered within the export instead, so the
    user's own messages read as conversations. Their own phone number is here,
    decrypted on the worker (D-061). Not here: reports about them (T-9.1),
    fraud signals, and moderation's own notes.
    """
    private = settings.R2_BUCKET_PRIVATE

    async def link(key: str | None) -> str | None:
        if key is None:
            return None
        return await storage.presign_get(private, key, int(EXPORT_LINK.total_seconds()))

    profile = await repository.profile_for_update(session, user.id)
    location = await repository.own_location(session, user.id)
    threads = await repository.threads(session, user.id)
    number_of = {thread.id: n for n, thread in enumerate(threads, start=1)}
    photos = []
    for photo in await repository.live_photos(session, user.id):
        live = photo.status.value != "rejected"
        photos.append(
            {
                "kind": photo.kind.value,
                "position": photo.position,
                "status": photo.status.value,
                "reject_reason": photo.reject_reason,
                "created_at": _iso(photo.created_at),
                "url": await link(photo.raw_key) if live else None,
            }
        )
    messages = []
    for row in await repository.sent_messages(session, user.id):
        messages.append(
            {
                "thread": number_of.get(row.thread_id),
                "kind": _plain(row.kind),
                "body": row.body,
                "duration_s": row.duration_s,
                "voice_url": await link(row.media_key),
                "created_at": _iso(row.created_at),
            }
        )
    prefs = await repository.notification_prefs(session, user.id)
    referral = await repository.referral(session, user.id)
    phone = None if user.phone_enc is None else decrypt_phone(user.phone_enc, settings)
    return {
        "export_version": EXPORT_VERSION,
        "app": APP_NAME,
        "generated_at": _iso(clock.now()),
        "account": {
            "id": str(user.id),
            "phone": phone,
            "gender": _plain(user.gender),
            "date_of_birth": _iso(user.dob),
            "role": _plain(user.role),
            "status": _plain(user.status),
            "onboarding_step": _plain(user.onboarding_step),
            "is_verified": user.is_verified,
            "has_pin": user.pin_hash is not None,
            "referral_code": user.referral_code,
            "created_at": _iso(user.created_at),
            "last_active_at": _iso(user.last_active_at),
        },
        "profile": {
            "first_name": profile.first_name,
            "username": profile.username,
            "about": profile.about,
            "hometown": profile.hometown,
            "city": profile.city,
            "area": (
                None
                if profile.area_id is None
                else await repository.area_name(session, profile.area_id)
            ),
            "location": (
                None
                if location is None
                else {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "updated_at": _iso(location.location_updated_at),
                }
            ),
            "seeking": _plain(profile.seeking),
            "intents": await repository.intent_labels(session, user.id),
            "interests": await repository.interest_labels(session, user.id),
            "settings": {
                "is_hidden": profile.is_hidden,
                "hide_age": profile.hide_age,
                "hide_distance": profile.hide_distance,
                "show_kudos": profile.show_kudos,
                "show_gifts": profile.show_gifts,
                "public_link": profile.public_link,
            },
        },
        "photos": photos,
        "selfie_checks": _rows(await repository.verifications(session, user.id)),
        "threads": [
            {
                "thread": number_of[thread.id],
                "origin": _plain(thread.origin),
                "status": _plain(thread.status),
                "opened_by_you": thread.opened_by == user.id,
                "created_at": _iso(thread.created_at),
                "knotted_at": _iso(thread.knotted_at),
                "expires_at": _iso(thread.expires_at),
            }
            for thread in threads
        ],
        "messages_sent": messages,
        "swipes": _rows(await repository.own_swipes(session, user.id)),
        "liked_you_reveals": _rows(await repository.own_reveals(session, user.id)),
        "blocks": _rows(await repository.own_blocks(session, user.id)),
        "reports_filed": _rows(await repository.reports_filed(session, user.id)),
        "kudos_given": _rows(await repository.kudos(session, user.id, "given")),
        "kudos_received": _rows(await repository.kudos(session, user.id, "received")),
        "gifts_sent": _rows(await repository.gifts(session, user.id, "sent")),
        "gifts_received": _rows(await repository.gifts(session, user.id, "received")),
        "album_requests_made": _rows(
            await repository.album_requests(session, user.id, "made")
        ),
        "album_requests_received": _rows(
            await repository.album_requests(session, user.id, "received")
        ),
        "balance": await repository.balance(session, user.id),
        "ledger": _rows(await repository.ledger(session, user.id)),
        "payments": _rows(await repository.payments(session, user.id)),
        "refund_requests": _rows(await repository.refund_requests(session, user.id)),
        "referred": (
            None
            if referral is None
            else {
                "created_at": _iso(referral.created_at),
                "rewarded_at": _iso(referral.rewarded_at),
            }
        ),
        "notifications": _rows(await repository.notifications(session, user.id)),
        "notification_settings": (
            None
            if prefs is None
            else {
                "match": prefs.match,
                "message": prefs.message,
                "like": prefs.like,
                "knot": prefs.knot,
                "expiry": prefs.expiry,
                "balance": prefs.balance,
                "gift": prefs.gift,
                "album": prefs.album,
                "generic_text": prefs.generic_text,
            }
        ),
        "sessions": _rows(await repository.sessions(session, user.id)),
    }


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _iso(value: datetime | date | None) -> str | None:
    return None if value is None else value.isoformat()


def _rows(rows: list[Any]) -> list[dict[str, Any]]:
    convert: Callable[[Any], Any] = lambda v: (
        _iso(v) if isinstance(v, (datetime, date)) else _plain(v)
    )
    return [
        {key: convert(value) for key, value in row._mapping.items()} for row in rows
    ]


# --- Erasing (D-500, D-503): the worker's half ----------------------------------------


async def erase_due_accounts(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    storage: StorageProvider,
    settings: Settings,
) -> int:
    """Erase every account deleted at least 29 days ago; how many were. One
    transaction each, so one that fails is left for tomorrow's run, still
    inside the 30 days, and the rest go on."""
    cutoff = clock.now() - ERASE_AFTER
    async with sessionmaker() as session, session.begin():
        due = await repository.accounts_due_for_erasure(session, cutoff)
    erased = 0
    for user_id in due:
        try:
            if await erase_account(sessionmaker, user_id, cutoff, storage, settings):
                erased += 1
        except Exception as error:  # noqa: BLE001 — the next run tries again
            log.error(
                "account.erase_failed", user_id=str(user_id), error=type(error).__name__
            )
    return erased


async def erase_account(
    sessionmaker: async_sessionmaker[AsyncSession],
    user_id: UUID,
    cutoff: datetime,
    storage: StorageProvider,
    settings: Settings,
) -> bool:
    """Erase one account, if it is still due: False if a sign-in restored it.

    Under the row's lock, which a sign-in on the number also takes: the files
    are deleted and read back as gone first, then the rows `erasure.ERASED`
    names, then the `users` row is anonymised. A file that won't go stops
    everything, rolled back, for the next run.
    """
    buckets = {
        "public": settings.R2_BUCKET_PUBLIC,
        "private": settings.R2_BUCKET_PRIVATE,
    }
    async with sessionmaker() as session, session.begin():
        user = await repository.account_for_erasure(session, user_id, cutoff)
        if user is None:
            return False
        files = await repository.files_to_erase(session, user_id)
        await delete_and_read_back(storage, [(buckets[b], key) for b, key in files])
        await repository.erase_rows(session, user_id)
        await anonymise(session, user)
    log.info("account.erased", user_id=str(user_id), files=len(files))
    return True


async def anonymise(session: AsyncSession, user: User) -> None:
    """The `users` row, kept because kept rows name it, emptied of the person:
    the number's encrypted copy, the date of birth (D-501), the PIN, the
    referral code they shared, when they were last seen. The number's hash stays
    (D-051), and so do gender (D-076 reads it) and role. One update, which the
    immutability trigger lets clear dob only because it sets `anonymised_at`."""
    user.phone_enc = None
    user.dob = None
    user.pin_hash = None
    user.pin_failed = 0
    user.referral_code = await users_service.fresh_referral_code(session)
    user.last_active_at = None
    user.anonymised_at = clock.now()
    await session.flush()


async def expire_due_exports(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    storage: StorageProvider,
    settings: Settings,
) -> int:
    """The daily job's other half: any export whose file outlived its link,
    because its own job never ran or kept failing. How many were expired."""
    now = clock.now()
    async with sessionmaker() as session, session.begin():
        due = await repository.exports_to_expire(session, now, now - STUCK_EXPORT)
    done = 0
    for export_id in due:
        try:
            if (
                await expire_export(
                    sessionmaker,
                    export_id=export_id,
                    storage=storage,
                    settings=settings,
                )
                == "expired"
            ):
                done += 1
        except Exception as error:  # noqa: BLE001 — the next run tries again
            log.error(
                "export.expire_failed",
                export_id=str(export_id),
                error=type(error).__name__,
            )
    return done


async def delete_and_read_back(
    storage: StorageProvider, objects: list[tuple[str, str]]
) -> None:
    """Delete each object, then read each back: success is every one gone
    (D-090). Storage that fails to answer counts as not gone."""
    for bucket, key in objects:
        try:
            await storage.delete(bucket, key)
        except Exception:  # noqa: BLE001, S112 — the read-back below decides
            continue
    remaining = 0
    for bucket, key in objects:
        try:
            await storage.head(bucket, key)
        except ObjectNotFound:
            continue
        except Exception:  # noqa: BLE001, S110 — unreadable is not proof it left
            pass
        remaining += 1
    if remaining:
        raise RuntimeError(f"{remaining} of {len(objects)} files are still stored")
