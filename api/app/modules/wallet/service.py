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

A transaction locks one wallet, or several in `user_id` order (D-077), and
the wallet refuses anything else (P-63): it records on the session which
wallets the transaction holds, and a lock below the highest held is a
`WalletMisuse`. A caller that will credit several men locks them first with
`lock_wallets()`, which sorts them; a wallet already held locks again freely.

**`reverse()` (T-8.2, D-520)** takes a payment's Velas back when its money goes
back: the same steps, but at step 6 it takes what the balance holds, down to 0,
never refusing, and writes nothing when that is 0. Only `purchase_reversal`,
and only `payments` calls it (`tests/modules/pricing/test_debit_callers.py`).

**Who may call `debit()` is checked each time it runs (P-152, D-651):** the
function that awaits it must be `pricing.service.charge` or gift sending's
`_send_in`, the two that price from a row, an admin's correction
(`admin.panel._correct`, T-9.5, D-923), or test code, which never ships
(`.dockerignore`). Anything else is refused before a row is read, a caller
reaching it by a name built at run time included, which the source scan in
`tests/modules/pricing/test_debit_callers.py` can't see. The scan stays, as the
second layer, and a test holds the two lists equal.

The owner's two reads, `balance()` and `ledger()`, are at the end (T-5.3),
and after them `reconcile()`, the worker's daily check that every balance is
the sum of its ledger (T-9.9, D-940).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from types import FrameType
from typing import Final
from uuid import UUID

import structlog
from pydantic import AwareDatetime
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from app.core import events
from app.core.enums import Gender, LedgerReason
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.modules.notifications import service as notifications_service
from app.modules.wallet import repository, rules, schemas
from app.modules.wallet.models import LedgerEntry
from app.modules.wallet.rules import Direction, Ref, RefType

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


@dataclass(frozen=True)
class Reversal:
    """What `reverse()` took and what it couldn't: `taken + shortfall` is the
    amount asked. `entry` is None when nothing was taken."""

    entry: LedgerEntry | None
    taken: int
    shortfall: int
    # False when the key was already in the ledger, or nothing was taken.
    applied: bool


class _NothingToTake(Exception):
    """A reversal found a balance of 0: nothing is written (D-520)."""


# The wallets the session's transaction has locked (P-63): read by every lock,
# forgotten when the transaction ends, since its locks end with it.
_HELD = "wallet.held"


@sa_event.listens_for(Session, "after_transaction_end")
def _forget_held(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is None:
        session.info.pop(_HELD, None)


def _held(session: AsyncSession) -> set[UUID]:
    held: set[UUID] = session.info.setdefault(_HELD, set())
    return held


async def _lock(session: AsyncSession, user_id: UUID) -> tuple[int, Gender | None]:
    """Lock one wallet, in `user_id` order with any this transaction holds:
    two transactions each holding one man's wallet and waiting for the other's
    is a deadlock Postgres breaks by failing one (D-077, P-63)."""
    held = _held(session)
    if user_id not in held and held and user_id < max(held):
        raise WalletMisuse(
            "wallets are locked in user_id order (D-077, P-63): "
            "lock_wallets() them first"
        )
    locked = await repository.lock_wallet(session, user_id)
    if locked is None:
        raise WalletMisuse("this user has no wallet; signup creates one (T-3.3)")
    held.add(user_id)
    return locked


async def lock_wallets(session: AsyncSession, user_ids: Iterable[UUID]) -> None:
    """Lock several wallets, sorted by `user_id`, before crediting them in
    whatever order: a referral's two men (T-8.6). Those already held are
    skipped; one below a wallet already held is still refused."""
    if not session.in_transaction():
        raise WalletMisuse("lock_wallets() runs only inside its caller's transaction")
    for user_id in sorted(set(user_ids) - _held(session)):
        await _lock(session, user_id)


# The only reasons `reverse()` takes: anything else that spends is priced and
# refused on a low balance (`debit`).
REVERSIBLE = frozenset({LedgerReason.PURCHASE_REVERSAL})

# (module, function) of everything that may await `debit()` (P-152, D-651): the
# two that price from a row, `action_prices` and `gifts`. An allowlist, so a
# caller nobody has named is refused, however it found the function.
DEBIT_CALLERS: Final = frozenset(
    {
        ("app.modules.pricing.service", "charge"),
        ("app.modules.gifts.service", "_send_in"),
        # An admin's correction (T-9.5, D-923): its amount is the admin's,
        # checked against the balance under the lock, never a price.
        ("app.modules.admin.panel", "_correct"),
    }
)
# Tests prove the wallet by calling it directly. They never ship: the image
# leaves `tests/` out (`.dockerignore`), so no deployed code has this name.
TESTS_PACKAGE: Final = "tests"


def _may_debit(caller: FrameType | None) -> bool:
    """Whether the frame awaiting `debit()` is one it answers to. None, or a
    frame from the event loop, is a call nobody named: refused."""
    if caller is None:
        return False
    module = caller.f_globals.get("__name__")
    if not isinstance(module, str):
        return False
    if module == TESTS_PACKAGE or module.startswith(TESTS_PACKAGE + "."):
        return True
    return (module, caller.f_code.co_qualname) in DEBIT_CALLERS


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
    that repeat (`admin_grant`, `thread_reopen`, `thread_extend`). The key is
    built here.
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
    `INSUFFICIENT_CREDITS` (402) having written nothing. Only `DEBIT_CALLERS`
    may await it (P-152, D-651)."""
    if not _may_debit(sys._getframe(1)):
        raise WalletMisuse(
            "debit() is awaited only by pricing.service.charge and gift sending, "
            "which price from a row (P-152, D-651)"
        )
    return await _apply(session, user_id, amount, reason, Direction.DEBIT, ref, event)


async def reverse(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    reason: LedgerReason,
    *,
    ref: Ref,
    event: str,
) -> Reversal:
    """Take back up to `amount` from a man's balance for `reason`: what he
    still holds, down to 0. Never `INSUFFICIENT_CREDITS`: money that went back
    takes its Velas back whether or not he spent them (D-520). The rest is the
    shortfall, the caller's to record. At 0 nothing is written."""
    if reason not in REVERSIBLE:
        raise WalletMisuse(f"{reason} is never taken by reverse(): debit() it (D-520)")
    try:
        result = await _apply(
            session, user_id, amount, reason, Direction.DEBIT, ref, event, at_most=True
        )
    except _NothingToTake:
        log.info("wallet.nothing_to_reverse", user_id=str(user_id), reason=str(reason))
        return Reversal(entry=None, taken=0, shortfall=amount, applied=False)
    taken = -result.entry.delta
    return Reversal(result.entry, taken, amount - taken, result.applied)


async def _apply(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    reason: LedgerReason,
    direction: Direction,
    ref: Ref | None,
    event: str | None,
    *,
    at_most: bool = False,
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

    balance, gender = await _lock(session, user_id)
    if gender is not Gender.MALE:
        raise WalletMisuse("only a man may hold credits (D-076)")

    existing = await repository.entry_by_key(session, key)
    if existing is not None:
        details = (user_id, reason, delta, ref_type, ref_id)
        if at_most and -amount <= existing.delta < 0:
            # A reversal took what the balance held then, at most the amount.
            details = (user_id, reason, existing.delta, ref_type, ref_id)
        if _details(existing) != details:
            raise WalletMisuse(
                f"{reason}: this event is in the ledger already, with other "
                "details; a key is never reused (D-077)"
            )
        log.info("wallet.repeated", user_id=str(user_id), reason=str(reason))
        return LedgerResult(existing, applied=False)

    if at_most:
        amount = min(balance, amount)
        if amount == 0:
            raise _NothingToTake
        delta = -amount
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
    if delta < 0:
        # T-9.4 (D-853): below `low_balance_velas` for the first time since he
        # was above it, a notification, in this transaction.
        await notifications_service.balance_fell(
            session, user_id, before=balance, after=balance_after
        )
    log.info(
        "wallet.applied",
        user_id=str(user_id),
        reason=str(reason),
        delta=delta,
        balance_after=balance_after,
    )
    return LedgerResult(entry, applied=True)


async def entry_for(
    session: AsyncSession, user_id: UUID, reason: LedgerReason, event: str
) -> LedgerEntry | None:
    """The entry a reason that repeats wrote for `event`, if any: a restore
    reads the reversal it undoes this way (D-520)."""
    if not rules.RULES[reason].caller_names_event:
        raise WalletMisuse(
            f"{reason} takes no event: the event is the ref's id (D-077)"
        )
    return await repository.entry_by_key(session, rules.key_for(user_id, reason, event))


async def reversed_net(session: AsyncSession, user_id: UUID, ref: Ref) -> int:
    """What reversals took for this ref, less what restores gave back: never
    below 0, since a restore gives back at most its own reversal (D-520)."""
    total = await repository.sum_for_ref(
        session,
        user_id,
        (LedgerReason.PURCHASE_REVERSAL, LedgerReason.PURCHASE_RESTORED),
        str(ref.type),
        ref.id,
    )
    return -total


async def referral_rewards_paid(session: AsyncSession, referrer_id: UUID) -> int:
    """How many referrals this man has been paid for as the referrer: his
    `referral_reward` entries naming someone else's referral, never his own
    as a referee (T-8.6, D-692). Read under his wallet's lock, so two rewards
    at once count each other."""
    if referrer_id not in _held(session):
        raise WalletMisuse("referral_rewards_paid() reads under the wallet's lock")
    return await repository.count_other_refs(
        session, referrer_id, LedgerReason.REFERRAL_REWARD, str(RefType.REFERRAL)
    )


def _details(
    entry: LedgerEntry,
) -> tuple[UUID, LedgerReason, int, str | None, UUID | None]:
    return entry.user_id, entry.reason, entry.delta, entry.ref_type, entry.ref_id


# --- The owner's reads (T-5.3) ---------------------------------------------------

# The ledger's sort key, `(created_at, id)` (D-270).
LEDGER_CURSOR: Cursor[tuple[datetime, UUID]] = Cursor(tuple[AwareDatetime, UUID])


async def balance(session: AsyncSession, user_id: UUID) -> schemas.Wallet:
    """The balance as it stands. Read, never refused: a woman's is 0 because
    D-076's triggers hold it there, so she gets 0 the same way a man gets his."""
    async with session.begin():
        return schemas.Wallet(balance=await repository.balance_of(session, user_id))


async def ledger(
    session: AsyncSession, user_id: UUID, params: PageParams
) -> schemas.LedgerEntryPage:
    """The user's entries, newest first by `(created_at, id)`. A woman's list
    is empty, as D-076's trigger keeps it, and never refused.

    A cursor names a position, never whose: the query is the caller's own
    ledger, whatever the cursor says (D-270).
    """
    after = None if params.cursor is None else LEDGER_CURSOR.decode(params.cursor)
    async with session.begin():
        rows = await repository.ledger_page(
            session, user_id, after=after, limit=params.fetch
        )
    entries = [schemas.LedgerEntry(**row._asdict()) for row in rows]
    return schemas.LedgerEntryPage.of(
        entries,
        params,
        lambda entry: LEDGER_CURSOR.encode((entry.created_at, entry.id)),
    )


# --- Reconciliation (T-9.9, D-940) -----------------------------------------------


@dataclass(frozen=True)
class Mismatch:
    user_id: UUID
    # None for ledger rows with no wallet: signup creates both, so a bug too.
    balance: int | None
    ledger_sum: int


async def reconcile(session: AsyncSession) -> list[Mismatch]:
    """Every balance that isn't the sum of its ledger, each logged at error
    level as `wallet.ledger_mismatch` (D-940); none is one `wallet.reconciled`
    line at info, so a quiet day still shows the check ran.

    Read-only: a mismatch is repaired by hand, from the ledger, which is
    append-only and complete (D-077's "detected, not prevented"). A line names
    the user by id, with their balance and ledger sum, and nothing else
    (rule 15).
    """
    async with session.begin():
        rows = await repository.mismatched_wallets(session)
    found = [
        Mismatch(
            user_id=row.user_id,
            balance=None if row.balance is None else int(row.balance),
            ledger_sum=int(row.ledger_sum),
        )
        for row in rows
    ]
    for mismatch in found:
        log.error(
            "wallet.ledger_mismatch",
            user_id=str(mismatch.user_id),
            balance=mismatch.balance,
            ledger_sum=mismatch.ledger_sum,
        )
    if not found:
        log.info("wallet.reconciled", mismatches=0)
    return found
