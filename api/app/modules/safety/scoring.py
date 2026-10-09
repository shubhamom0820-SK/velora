"""Scoring and its actions (T-9.2, D-031, D-900 to D-906).

`recompute` reads one person's signals since `counted_from` (all of them, if
it is unset) and their last 7 days, writes `fraud_scores`, and acts on the band:

- **shadow:** nothing more here. Every list already shows a shadowed person
  only to the shadowed (`discovery.repository.visible_to`), and drops them back
  in as the score decays.
- **freeze,** whenever the band is freeze and the account can sign in: `frozen`, every session revoked
  and every socket closed in this transaction (D-557), the freeze written to
  `audit_log` as the system user (D-905), and a warning logged for whoever
  watches (D-904). Only an account that can sign in is frozen (D-902). Nothing
  here ever lifts a freeze: a person does, with `app.tools.unfreeze` (D-906)
  until T-9.5 gives it a screen.

It runs for the person reported, in the report's own transaction, and for
everyone with a recent signal or a score to decay, every 10 minutes in the
worker's own loop (`recompute_fraud`). The person's row is locked first, so
two reports at once are counted one after the other, and two workers never
score one person at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import FraudBand, Role, UserStatus
from app.modules.admin import service as admin_service
from app.modules.auth import service as auth_service
from app.modules.safety import fraud, repository
from app.modules.users.models import User

log = structlog.get_logger(__name__)

FREEZE: Final = "fraud.freeze"
BAND: Final = "fraud.band"
UNFREEZE: Final = "fraud.unfreeze"


@dataclass(frozen=True)
class Outcome:
    score: int
    band: FraudBand
    frozen: bool


async def recompute(
    session: AsyncSession, user_id: UUID, *, skip_locked: bool = False
) -> Outcome | None:
    """`user_id`'s score, band and actions, in the caller's transaction. None
    if there is no such user, or, with `skip_locked`, another holds them."""
    user = await repository.lock_user(session, user_id, skip_locked=skip_locked)
    if user is None or user.id == admin_service.SYSTEM_USER_ID:
        return None
    now = clock.now()
    saved = await repository.score_of(session, user_id)
    counted_from = saved.counted_from if saved is not None else None
    since = _later(now - fraud.DECAY, counted_from)
    rows = await repository.events_since(session, user_id, since)
    scored = fraud.score(
        fraud.Event(
            signal=row.signal,
            weight=row.weight,
            age=now - row.created_at,
            reporter=row.reporter_id,
        )
        for row in rows
    )
    numbers = await repository.reporting_numbers(
        session, user_id, _later(now - fraud.REPORTS_WINDOW, counted_from)
    )
    band = fraud.band(scored.score, reporting_numbers=numbers)
    before = saved.band if saved is not None else FraudBand.NORMAL
    await repository.save_score(
        session,
        user_id,
        score=scored.score,
        band=band,
        signals=scored.signals,
        counted_from=counted_from,
    )
    if band is not before and (band in fraud.ACTED or before in fraud.ACTED):
        await admin_service.audit(
            session,
            admin_service.SYSTEM_USER_ID,
            BAND,
            {"from": before.value, "to": band.value, "score": scored.score},
            target=("user", user_id),
        )
    frozen = False
    # Whenever the band is freeze, not only on the way in: an account the
    # band reached while it couldn't be frozen (deleted, then restored by
    # signing in again) is frozen once it can be. `_freeze` asks the status,
    # so a frozen account is never frozen twice.
    if band is FraudBand.FREEZE:
        rule = "reports" if numbers >= fraud.REPORTS_TO_FREEZE else "score"
        frozen = await _freeze(session, user, score=scored.score, rule=rule)
    return Outcome(score=scored.score, band=band, frozen=frozen)


def _later(a: datetime, b: datetime | None) -> datetime:
    return a if b is None or a >= b else b


async def _freeze(session: AsyncSession, user: User, *, score: int, rule: str) -> bool:
    """D-031's freeze, if the account is one that can sign in (D-902)."""
    if user.status not in fraud.FREEZABLE:
        return False
    user.status = UserStatus.FROZEN
    await auth_service.sign_out_everywhere(session, user.id)
    await admin_service.audit(
        session,
        admin_service.SYSTEM_USER_ID,
        FREEZE,
        {"rule": rule, "score": score},
        target=("user", user.id),
    )
    log.warning("fraud.frozen", user_id=str(user.id), rule=rule, score=score)
    return True


# --- The founder's undo (D-906) --------------------------------------------------------


class NotFrozen(Exception):
    """The account isn't frozen: nothing to lift."""


class NotAnAdmin(Exception):
    """Whoever is named as lifting it isn't an active admin."""


@dataclass(frozen=True)
class Lifted:
    score_before: int
    band_before: FraudBand


async def unfreeze(
    session: AsyncSession, user_id: UUID, *, by: UUID, reason: str
) -> Lifted:
    """Lift `user_id`'s freeze, whoever froze it, and start their score again
    from now, in the caller's transaction: `active`, the score 0 and normal,
    and only signals from now on counting (D-906). Written to `audit_log` as
    `by`, an active admin. Nothing else: no session is made, no message read.
    LookupError if there is no such account."""
    admin = await repository.lock_user(session, by)
    if (
        admin is None
        or admin.role is not Role.ADMIN
        or admin.status is not UserStatus.ACTIVE
    ):
        raise NotAnAdmin
    user = await repository.lock_user(session, user_id)
    if user is None or user.id == admin_service.SYSTEM_USER_ID:
        raise LookupError("no such account")
    if user.status is not UserStatus.FROZEN:
        raise NotFrozen
    saved = await repository.score_of(session, user_id)
    lifted = Lifted(
        score_before=saved.score if saved is not None else 0,
        band_before=saved.band if saved is not None else FraudBand.NORMAL,
    )
    user.status = UserStatus.ACTIVE
    await repository.save_score(
        session,
        user_id,
        score=0,
        band=FraudBand.NORMAL,
        signals={},
        counted_from=clock.now(),
    )
    await admin_service.audit(
        session,
        by,
        UNFREEZE,
        {
            "reason": reason,
            "score_before": lifted.score_before,
            "band_before": lifted.band_before.value,
        },
        target=("user", user_id),
    )
    return lifted
