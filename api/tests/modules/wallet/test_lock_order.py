"""P-63: a transaction locks wallets in `user_id` order, and the wallet refuses
anything else (D-077). Worst case without it: two transactions each holding
one man's wallet and waiting for the other's, a deadlock Postgres breaks by
failing one at random. The first referral reward to credit two men is
T-8.6's.

The guard's tests run in the `db` fixture's rolled-back transaction. The race
needs two connections, so its two men are committed (tests/committed.py), but
it only locks their wallets: nothing is credited, so no ledger row is ever
committed.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import LedgerReason
from app.modules.wallet import service
from app.modules.wallet.models import Wallet
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import WalletMisuse
from tests.committed import fresh_man
from tests.conftest import MakeUser

GRANT = LedgerReason.ADMIN_GRANT
# A grant names its audit row (D-923); no FK, so any id.
AUDIT = Ref(RefType.AUDIT_LOG, uuid.uuid4())


async def _low_high(make_user: MakeUser) -> tuple[uuid.UUID, uuid.UUID]:
    a, _ = await make_user()
    b, _ = await make_user()
    low, high = sorted((a.id, b.id))
    return low, high


async def _entries(db: AsyncSession, *user_ids: uuid.UUID) -> int:
    count = await db.scalar(
        text("select count(*) from ledger_entries where user_id = any(:u)"),
        {"u": list(user_ids)},
    )
    return int(count or 0)


@pytest.mark.critical  # P-63: no deadlock between two men's wallets
async def test_a_wallet_below_one_held_is_refused_and_nothing_is_written(
    db: AsyncSession, make_user: MakeUser
) -> None:
    low, high = await _low_high(make_user)
    await service.credit(db, high, 3, GRANT, ref=AUDIT, event="first")

    with pytest.raises(WalletMisuse, match="user_id order"):
        await service.credit(db, low, 3, GRANT, ref=AUDIT, event="second")

    assert await _entries(db, low) == 0


async def test_in_order_both_apply(db: AsyncSession, make_user: MakeUser) -> None:
    low, high = await _low_high(make_user)

    await service.credit(db, low, 3, GRANT, ref=AUDIT, event="first")
    await service.credit(db, high, 3, GRANT, ref=AUDIT, event="second")

    assert await _entries(db, low, high) == 2


async def test_a_wallet_already_held_locks_again_whatever_its_place(
    db: AsyncSession, make_user: MakeUser
) -> None:
    low, high = await _low_high(make_user)
    await service.credit(db, low, 3, GRANT, ref=AUDIT, event="first")
    await service.credit(db, high, 3, GRANT, ref=AUDIT, event="second")

    await service.credit(db, low, 3, GRANT, ref=AUDIT, event="third")

    assert await _entries(db, low, high) == 3


@pytest.mark.parametrize("given", ["ascending", "descending"])
async def test_lock_wallets_sorts_them_so_any_order_of_credits_applies(
    db: AsyncSession, make_user: MakeUser, given: str
) -> None:
    low, high = await _low_high(make_user)
    ids = [low, high] if given == "ascending" else [high, low]

    await service.lock_wallets(db, ids)
    await service.credit(db, high, 3, GRANT, ref=AUDIT, event="first")
    await service.credit(db, low, 3, GRANT, ref=AUDIT, event="second")

    assert await _entries(db, low, high) == 2


async def test_lock_wallets_still_refuses_one_below_a_wallet_held(
    db: AsyncSession, make_user: MakeUser
) -> None:
    low, high = await _low_high(make_user)
    await service.credit(db, high, 3, GRANT, ref=AUDIT, event="first")

    with pytest.raises(WalletMisuse, match="user_id order"):
        await service.lock_wallets(db, [low, high])


async def test_what_a_transaction_holds_ends_with_it(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A commit ends the locks, so the next transaction starts holding none:
    the lower wallet locks freely after it."""
    low, high = await _low_high(make_user)
    await service.credit(db, high, 3, GRANT, ref=AUDIT, event="first")
    await db.commit()
    await db.connection()

    await service.credit(db, low, 3, GRANT, ref=AUDIT, event="second")

    assert await _entries(db, low, high) == 2


async def test_lock_wallets_outside_a_transaction_is_refused(
    db: AsyncSession, make_user: MakeUser
) -> None:
    low, high = await _low_high(make_user)
    await db.commit()

    with pytest.raises(WalletMisuse, match="transaction"):
        await service.lock_wallets(db, [low, high])


async def test_a_user_with_no_wallet_is_refused_by_lock_wallets(
    db: AsyncSession,
) -> None:
    await db.connection()
    with pytest.raises(WalletMisuse, match="no wallet"):
        await service.lock_wallets(db, [uuid.uuid4()])


# --- The race: two transactions, the same two men, opposite orders ---------------


@pytest.mark.critical  # P-63: the deadlock the guard exists to prevent
async def test_two_transactions_locking_two_men_in_opposite_orders_never_deadlock(
    test_engine: AsyncEngine,
) -> None:
    """Forced, not hoped for: each transaction holds its first wallet before
    either asks for its second. One asks low then high; the other high then
    low, and is refused at once, before it waits. So the first gets both and
    commits. With the guard gone, each waits for the other's wallet and
    Postgres breaks the deadlock by failing one (`40P01`)."""
    low, high = sorted([await fresh_man(test_engine), await fresh_man(test_engine)])
    both_hold_one = asyncio.Event()
    holding = 0
    errors: dict[str, BaseException] = {}

    async def run(name: str, first: uuid.UUID, second: uuid.UUID) -> None:
        nonlocal holding
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            try:
                async with session.begin():
                    await session.execute(text("set local deadlock_timeout = '100ms'"))
                    await service.lock_wallets(session, [first])
                    holding += 1
                    if holding == 2:
                        both_hold_one.set()
                    await asyncio.wait_for(both_hold_one.wait(), 10)
                    await service.lock_wallets(session, [second])
                    assert (
                        await session.scalar(
                            select(Wallet.balance).where(Wallet.user_id == second)
                        )
                        == 0
                    )
            except Exception as error:  # noqa: BLE001 — the test reads it
                errors[name] = error

    await asyncio.wait_for(
        asyncio.gather(run("in order", low, high), run("reversed", high, low)), 30
    )

    assert holding == 2  # both held one wallet before either asked for a second
    assert set(errors) == {"reversed"}, errors
    assert isinstance(errors["reversed"], WalletMisuse)
    assert not any(isinstance(e, DBAPIError) for e in errors.values())
