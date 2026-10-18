"""Reconciliation (T-9.9, D-940): every wallet's balance is the sum of its
ledger, checked by `wallet.service.reconcile()`, which the worker runs daily
(`tests/workers/test_reconcile_ledger.py`).

The check is global by design, so a test that makes a mismatch makes it
inside the rolled-back transaction, never committed (06-TESTING): `db.commit()`
here only releases a savepoint. Every assertion about a mismatch is scoped to
the users the test made.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.wallet import service as wallet_service
from app.modules.wallet.service import Mismatch
from tests.conftest import CapturedLogs, MakeUser


async def _reconcile(db: AsyncSession) -> list[Mismatch]:
    await db.commit()  # the check opens its own transaction, as the job's does
    return await wallet_service.reconcile(db)


def _mine(found: list[Mismatch], *user_ids: uuid.UUID) -> list[Mismatch]:
    return [m for m in found if m.user_id in user_ids]


def _lines(captured: CapturedLogs, event: str) -> list[dict[str, object]]:
    return [dict(e) for e in captured.events if e["event"] == event]


@pytest.mark.critical  # 06-TESTING's 5: balance == sum(delta) for every wallet
async def test_every_wallet_in_the_database_is_the_sum_of_its_ledger(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    """Every wallet this run's tests have committed, and this test's own: one
    granted through the wallet and one a woman's, at 0 with no rows."""
    await make_user(credits=7)
    await make_user(Gender.FEMALE)

    found = await _reconcile(db)

    assert found == []
    assert _lines(captured_logs, "wallet.ledger_mismatch") == []
    assert _lines(captured_logs, "wallet.reconciled") == [
        {"event": "wallet.reconciled", "log_level": "info", "mismatches": 0}
    ]


async def test_a_balance_written_outside_the_wallet_is_found_and_logged_as_an_error(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    """D-077's "detected, not prevented": the app role can write a balance,
    so the ledger's sum is the authority, and a balance moved by anything but
    the wallet is a mismatch, its line naming the man by id and nothing else
    (rule 15)."""
    man, _ = await make_user(credits=5)
    man_id = man.id
    await db.execute(
        text("UPDATE wallets SET balance = 7 WHERE user_id = :u"), {"u": man_id}
    )

    found = await _reconcile(db)

    assert _mine(found, man_id) == [Mismatch(man_id, 7, 5)]
    assert [
        line
        for line in _lines(captured_logs, "wallet.ledger_mismatch")
        if line["user_id"] == str(man_id)
    ] == [
        {
            "event": "wallet.ledger_mismatch",
            "log_level": "error",
            "user_id": str(man_id),
            "balance": 7,
            "ledger_sum": 5,
        }
    ]
    # The quiet day's line is for a quiet day only.
    assert _lines(captured_logs, "wallet.reconciled") == []
    captured_logs.assert_listening()


async def test_a_ledger_row_the_balance_never_took_is_found_the_other_way(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """An entry written beside the wallet, not through it: the sum moves and
    the balance doesn't."""
    man, _ = await make_user(credits=5)
    man_id = man.id
    await db.execute(
        text(
            "INSERT INTO ledger_entries (user_id, delta, balance_after, reason,"
            " ref_type, ref_id, idempotency_key) VALUES (:u, 3, 8, 'admin_grant',"
            " 'audit_log', :ref, :key)"
        ),
        {"u": man_id, "ref": uuid.uuid4(), "key": f"t99-beside-{uuid.uuid4()}"},
    )

    found = await _reconcile(db)

    assert _mine(found, man_id) == [Mismatch(man_id, 5, 8)]


async def test_balances_that_agree_are_never_reported(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """A man with Velas, a man with none, and a woman, who has no rows and a 0
    the database holds there (D-076): none of them is a mismatch, while a
    broken wallet beside them is."""
    rich, _ = await make_user(credits=9)
    poor, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    broken, _ = await make_user(credits=2)
    ids = (rich.id, poor.id, woman.id, broken.id)
    await db.execute(
        text("UPDATE wallets SET balance = 0 WHERE user_id = :u"), {"u": broken.id}
    )

    found = await _reconcile(db)

    assert _mine(found, *ids) == [Mismatch(broken.id, 0, 2)]


async def test_a_balance_with_no_ledger_rows_at_all_is_found(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Nothing in the ledger to sum: the full join still finds the wallet."""
    man, _ = await make_user()
    man_id = man.id
    await db.execute(
        text("UPDATE wallets SET balance = 4 WHERE user_id = :u"), {"u": man_id}
    )

    found = await _reconcile(db)

    assert _mine(found, man_id) == [Mismatch(man_id, 4, 0)]


async def test_ledger_rows_with_no_wallet_are_found(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Signup creates both, so a wallet gone is a bug too: the full join finds
    the ledger's side, its balance None."""
    man, _ = await make_user(credits=6)
    man_id = man.id
    await db.execute(text("DELETE FROM wallets WHERE user_id = :u"), {"u": man_id})

    found = await _reconcile(db)

    assert _mine(found, man_id) == [Mismatch(man_id, None, 6)]
