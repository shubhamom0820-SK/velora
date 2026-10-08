"""Events for a user's open sockets (02-ARCHITECTURE §6), published after the
fact, never under a lock.

A service queues an event in the transaction that makes it true:
`events.queue(session, user_id, "wallet.updated", {"balance": 12})`. It is kept
if that transaction commits and dropped if it rolls back, a savepoint's
rollback included. When the request ends, `get_session` publishes the
request's committed events to Redis `user:{id}`, in §6's envelope, after the
session has closed. So nothing external runs while a row is locked, and an
event never announces something that didn't happen.

The publish is awaited, never fire-and-forget: one that outlived its request
would fail where nobody is looking. A failure is logged and never fails the
request, whose transaction has already committed; that includes a Redis that
accepts the connection and never answers, cut off after `PUBLISH_TIMEOUT_S`.
Code outside a request (the seed, a test's session) publishes nothing.
T-7.4 builds the socket side (`modules/realtime`).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

log = structlog.get_logger(__name__)

PUBLISH_TIMEOUT_S = 1.0

# A user's sockets close (T-7.4): queued in the transaction that revokes their
# sessions, so a signed-out device stops hearing. The gateway acts on it and
# never sends it to a client.
CLOSE_SOCKETS = "socket.close"

# On `Session.info`: (the transaction it was queued in, the event).
_PENDING = "events.pending"
_COMMITTED = "events.committed"


@dataclass(frozen=True)
class Event:
    user_id: uuid.UUID
    type: str
    data: dict[str, Any]

    @property
    def channel(self) -> str:
        return f"user:{self.user_id}"

    def envelope(self) -> str:
        return json.dumps(
            {"type": self.type, "id": str(uuid.uuid4()), "data": self.data}
        )


def queue(
    session: AsyncSession, user_id: uuid.UUID, type_: str, data: dict[str, Any]
) -> None:
    """Queue an event in the innermost transaction open on `session`."""
    sync = session.sync_session
    transaction = sync.get_nested_transaction() or sync.get_transaction()
    if transaction is None:
        raise RuntimeError(
            "An event is queued inside the transaction that makes it true."
        )
    pending: list[tuple[SessionTransaction, Event]] = sync.info.setdefault(_PENDING, [])
    pending.append((transaction, Event(user_id, type_, data)))


def close_sockets(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Close every socket `user_id` has open, once this transaction commits."""
    queue(session, user_id, CLOSE_SOCKETS, {})


def take_committed(session: AsyncSession) -> list[Event]:
    """The events `session`'s committed transactions queued, handed over once."""
    committed: list[Event] = session.sync_session.info.pop(_COMMITTED, [])
    return committed


async def publish(events: Sequence[Event], redis: Redis) -> None:
    if not events:
        return
    try:
        async with asyncio.timeout(PUBLISH_TIMEOUT_S):
            for each in events:
                await redis.publish(each.channel, each.envelope())
    except Exception as error:  # noqa: BLE001 — whatever failed, the request stands
        # The error's class only: a Redis error's text can carry its address.
        log.warning(
            "events.publish_failed",
            events=len(events),
            types=sorted({each.type for each in events}),
            error=type(error).__name__,
        )


# --- Kept on commit, dropped on rollback ------------------------------------------
#
# SQLAlchemy calls `after_commit` when a savepoint is released too, so only the
# outermost commit keeps anything; a released savepoint's events wait for it.


@event.listens_for(Session, "after_commit")
def _keep_committed(session: Session) -> None:
    if session.in_nested_transaction():
        return
    pending = session.info.pop(_PENDING, [])
    if pending:
        session.info.setdefault(_COMMITTED, []).extend(e for _, e in pending)


@event.listens_for(Session, "after_soft_rollback")
def _drop_rolled_back(
    session: Session, previous_transaction: SessionTransaction
) -> None:
    pending = session.info.get(_PENDING)
    if pending:
        session.info[_PENDING] = [
            (transaction, each)
            for transaction, each in pending
            if not _inside(transaction, previous_transaction)
        ]


@event.listens_for(Session, "after_transaction_end")
def _forget_uncommitted(session: Session, transaction: SessionTransaction) -> None:
    """The outermost transaction ended: anything still pending never committed
    (a session closed with its transaction open sends no rollback event)."""
    if transaction.parent is None:
        session.info.pop(_PENDING, None)


def _inside(
    transaction: SessionTransaction | None, ancestor: SessionTransaction
) -> bool:
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False
