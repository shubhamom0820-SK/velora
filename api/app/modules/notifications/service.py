"""Notifications (T-9.4): the one way anything tells a person something, the
in-app list, push subscriptions and the settings.

**`notify()`** is called in the transaction that makes a thing true, as
`events.queue` is, and only there: so a rollback tells nobody. It writes, for
an active account only (`rules.TOLD`; a paused one is sent nothing, T-9.6):
- the in-app row, unless the kind is push-only (D-852);
- a push in `push_outbox`, when the kind's setting is on and the person has a
  subscription, and a wake for the worker once the transaction commits
  (`events.wake_push`, D-850). The worker reads the setting and the status
  again when it sends, so a change in between still counts.

A kind only a man is told (`rules.MEN_ONLY`: an hour running out, a balance) is
never written for anyone else (D-554, P-460). A like to a man never names who
(D-542): the payload loses `user_id` here, before anything is written.
"""

from __future__ import annotations

from typing import Any, Final
from uuid import UUID

import structlog
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.modules.admin import service as admin_service
from app.modules.likes import rules as likes_rules
from app.modules.notifications import repository, rules, schemas
from app.modules.notifications.rules import Kind
from app.modules.users.models import User

log = structlog.get_logger(__name__)

LOW_BALANCE_KEY: Final = "low_balance_velas"

# The list's sort key, `(created_at, id)` (D-270).
NOTIFICATIONS_CURSOR = Cursor(tuple[AwareDatetime, UUID])


async def notify(
    session: AsyncSession, user_id: UUID, kind: Kind, payload: dict[str, Any]
) -> bool:
    """Tell `user_id` about `kind`, in the caller's transaction. Whether
    anything was written."""
    if not session.in_transaction():
        raise RuntimeError(
            "A notification is written in the transaction that makes it true."
        )
    row = await repository.recipient(session, user_id, rules.PREF_FOR[kind])
    if row is None:
        return False
    status, gender, wanted, subscribed = row
    if not rules.told(status) or not rules.reaches(kind, gender):
        return False
    if kind is Kind.LIKE and not likes_rules.sees_everyone(gender):
        payload = {key: value for key, value in payload.items() if key != "user_id"}
    if kind not in rules.PUSH_ONLY:
        repository.add(session, user_id, str(kind), payload)
    if wanted and subscribed:
        repository.add_push(session, user_id, str(kind), payload)
        events.wake_push(session, user_id)
    return True


async def balance_fell(
    session: AsyncSession, user_id: UUID, *, before: int, after: int
) -> None:
    """A debit took a man's balance from `low_balance_velas` or more to below
    it (D-853): one `low_balance`, per crossing, never per debit below it."""
    if after >= before:
        return
    low = await admin_service.config_int(session, LOW_BALANCE_KEY)
    if before >= low > after:
        await notify(session, user_id, Kind.LOW_BALANCE, {"balance": after})


# --- The in-app list -------------------------------------------------------------


async def notifications(
    session: AsyncSession, user: User, params: PageParams
) -> schemas.NotificationPage:
    """The caller's own, newest first, whatever the cursor says (D-270)."""
    after = (
        None if params.cursor is None else NOTIFICATIONS_CURSOR.decode(params.cursor)
    )
    async with session.begin():
        rows = await repository.page(session, user.id, after=after, limit=params.fetch)
    items = [
        schemas.Notification(
            id=row.id,
            kind=row.kind,
            data=row.payload or {},
            read_at=row.read_at,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return schemas.NotificationPage.of(
        items,
        params,
        lambda item: NOTIFICATIONS_CURSOR.encode((item.created_at, item.id)),
    )


async def mark_read(session: AsyncSession, user: User) -> None:
    """Every unread notification of the caller's, read now."""
    async with session.begin():
        await repository.mark_read(session, user.id, clock.now())


# --- Settings --------------------------------------------------------------------


def _prefs_view(row: Any) -> schemas.Prefs:
    return schemas.Prefs(
        **{field: getattr(row, field) for field in schemas.Prefs.model_fields}
    )


def _no_prefs() -> RuntimeError:
    # Signup writes the row (T-3.3) and only the erasure removes it.
    return RuntimeError("a signed-in user has notification_prefs")


async def prefs(session: AsyncSession, user: User) -> schemas.Prefs:
    async with session.begin():
        row = await repository.prefs(session, user.id)
        if row is None:
            raise _no_prefs()
        return _prefs_view(row)


async def update_prefs(
    session: AsyncSession, user: User, patch: schemas.PrefsPatch
) -> schemas.Prefs:
    async with session.begin():
        row = await repository.prefs_for_update(session, user.id)
        if row is None:
            raise _no_prefs()
        for field in patch.model_fields_set:
            value = getattr(patch, field)
            if value is not None:
                setattr(row, field, value)
        await session.flush()
        return _prefs_view(row)


# --- Subscriptions ---------------------------------------------------------------


def push_key(settings: Settings) -> schemas.PushKey:
    """The VAPID public key, or `NOT_FOUND` where push isn't set up (local and
    CI, D-856): the web then offers no push."""
    if settings.PUSH_PROVIDER != "webpush" or not settings.VAPID_PUBLIC_KEY:
        raise AppError(
            "NOT_FOUND", "Push notifications aren't available here.", status=404
        )
    return schemas.PushKey(public_key=settings.VAPID_PUBLIC_KEY)


async def subscribe(
    session: AsyncSession, user: User, body: schemas.PushSubscriptionIn
) -> None:
    async with session.begin():
        await repository.subscribe(
            session, user.id, body.endpoint, body.keys.p256dh, body.keys.auth
        )
        await repository.keep_newest(session, user.id, rules.SUBSCRIPTIONS_KEPT)
    # Never the endpoint: it is a capability to push to that browser.
    log.info("push.subscribed", user_id=str(user.id))


async def unsubscribe(
    session: AsyncSession, user: User, body: schemas.PushSubscriptionOut
) -> None:
    """The caller's own subscription at `endpoint`, gone; anyone else's, and
    one that isn't there, untouched, and the same answer."""
    async with session.begin():
        await repository.unsubscribe(session, user.id, body.endpoint)
