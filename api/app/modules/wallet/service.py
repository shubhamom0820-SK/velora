"""Every change to a balance: `debit()` and `credit()` (CLAUDE.md rule 5).

Each runs inside its caller's transaction, beside whatever the money buys, so
both happen or neither does (02-ARCHITECTURE §9). In this order:

1. Refuse to run outside a transaction.
2. The amount is an `int`, never a `bool`, above 0.
3. The reason is used in its direction, with the ref and event it takes
   (`rules.py`); bare `refund` is refused.
4. Lock the wallet row, read the owner's gender, and refuse anyone but a man
   (D-076; the database refuses too).
5. A key already in the ledger with the same details returns that entry,
   `applied=False`; with different details it raises, since returning the
   earlier entry would hide the bug that reused the key (D-077). The check runs
   after the lock is granted, so under READ COMMITTED it sees a concurrent
   call's committed entry.
6. A debit needs the balance, or `INSUFFICIENT_CREDITS`.
7. Write the balance and the entry, and queue `wallet.updated`.

A unique violation is never caught: the transaction aborts, balance included.
Nothing external runs under the lock; the event is published after the request
(`core/events.py`). The wallet never checks a user's status: a frozen man's
captured payment is still credited (D-077).

A transaction locks one wallet, or several in `user_id` order (D-077).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, LedgerReason
from app.core.errors import AppError
from app.modules.wallet import repository, rules
from app.modules.wallet.models import LedgerEntry
from app.modules.wallet.rules import Direction, Ref

log = structlog.get_logger(__name__)


class WalletMisuse(Exception):
    """A caller broke the wallet's contract: a bug, never the user's doing, so
    it reaches them as a 500. Its message names the rule, never the key or the
    event (rule 15)."""


@dataclass(frozen=True)
class LedgerResult:
    entry: LedgerEntry
    # False when the key was already in the ledger: nothing changed this time.
    applied: bool


async def credit(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    reason: LedgerReason,
    *,
    ref: Ref | None = None,
    event: str | None = None,
) -> LedgerResult:
    """Add `amount` to a man's balance for `reason`.

    `ref` names the row that justifies it; `event` is named only by reasons
    that repeat (`admin_grant`, `thread_reopen`). The key is built here.
    """
    return await _apply(session, user_id, amount, reason, Direction.CREDIT, ref, event)


async def debit(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    reason: LedgerReason,
    *,
    ref: Ref | None = None,
    event: str | None = None,
) -> LedgerResult:
    """Take `amount` from a man's balance for `reason`, or raise
    `INSUFFICIENT_CREDITS` (402) having written nothing."""
    return await _apply(session, user_id, amount, reason, Direction.DEBIT, ref, event)


async def _apply(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    reason: LedgerReason,
    direction: Direction,
    ref: Ref | None,
    event: str | None,
) -> LedgerResult:
    if not session.in_transaction():
        raise WalletMisuse(
            f"{direction}() runs only inside its caller's transaction (D-077)"
        )
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise WalletMisuse("the amount must be a whole number above 0")
    if (problem := rules.entry_problem(reason, direction, ref, event)) is not None:
        raise WalletMisuse(f"{reason} {problem}")
    key = rules.key_for(user_id, reason, rules.event_for(reason, ref, event))
    delta = amount if direction is Direction.CREDIT else -amount
    ref_type = None if ref is None else str(ref.type)
    ref_id = None if ref is None else ref.id

    locked = await repository.lock_wallet(session, user_id)
    if locked is None:
        raise WalletMisuse("this user has no wallet; signup creates one (T-3.3)")
    balance, gender = locked
    if gender is not Gender.MALE:
        raise WalletMisuse("only a man may hold credits (D-076)")

    existing = await repository.entry_by_key(session, key)
    if existing is not None:
        details = (user_id, reason, delta, ref_type, ref_id)
        if _details(existing) != details:
            raise WalletMisuse(
                f"{reason}: this event is in the ledger already, with other "
                "details; a key is never reused (D-077)"
            )
        log.info("wallet.repeated", user_id=str(user_id), reason=str(reason))
        return LedgerResult(existing, applied=False)

    if direction is Direction.DEBIT and balance < amount:
        raise AppError(
            "INSUFFICIENT_CREDITS",
            "Your balance is too low for this.",
            status=402,
            details={"required": amount, "balance": balance},
        )

    balance_after = balance + delta
    await repository.set_balance(session, user_id, balance_after)
    entry = await repository.add_entry(
        session,
        user_id=user_id,
        delta=delta,
        balance_after=balance_after,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
        key=key,
    )
    events.queue(session, user_id, "wallet.updated", {"balance": balance_after})
    log.info(
        "wallet.applied",
        user_id=str(user_id),
        reason=str(reason),
        delta=delta,
        balance_after=balance_after,
    )
    return LedgerResult(entry, applied=True)


def _details(
    entry: LedgerEntry,
) -> tuple[UUID, LedgerReason, int, str | None, UUID | None]:
    return entry.user_id, entry.reason, entry.delta, entry.ref_type, entry.ref_id
