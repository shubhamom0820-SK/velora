"""T-9.2's signals, written by the services that see them, in their own
transactions (D-900). Apart from `safety.service`, whose reports and blocks
reach into albums and discovery, so that sign-in, profiles, Threads and
messages can write one without importing all of that.

Each is what was seen, never the person's words, position or number: a
report's id and reason, a count, a distance in kilometres. A threshold signal
is written at most once in `fraud.ONCE_PER`: crossing the line again the same
day says nothing new.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import ReportReason
from app.modules.safety import fraud, repository
from app.modules.safety.models import FraudEvent


def record_report_received(
    session: AsyncSession, reported_id: UUID, *, report_id: UUID, reason: ReportReason
) -> None:
    """A report about `reported_id`. The report names its reporter, so this
    doesn't; scoring counts one per reporter through it."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=reported_id,
            signal=fraud.REPORT_RECEIVED,
            weight=fraud.WEIGHTS[fraud.REPORT_RECEIVED],
            meta={"report_id": str(report_id), "reason": reason.value},
        ),
    )


def record_contact_masked(session: AsyncSession, user_id: UUID) -> None:
    """A message of `user_id`'s had a contact detail masked (D-030). Not which,
    and never the message."""
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id,
            signal=fraud.CONTACT_MASKED,
            weight=fraud.WEIGHTS[fraud.CONTACT_MASKED],
        ),
    )


async def record_crossing(
    session: AsyncSession, user_id: UUID, signal: str, meta: dict[str, Any]
) -> bool:
    """A threshold `signal` crossed, unless one was written in the last
    `fraud.ONCE_PER`. Whether it was written."""
    since = clock.now() - fraud.ONCE_PER
    if await repository.has_signal_since(session, user_id, signal, since):
        return False
    repository.add_fraud_event(
        session,
        FraudEvent(
            user_id=user_id, signal=signal, weight=fraud.WEIGHTS[signal], meta=meta
        ),
    )
    return True
