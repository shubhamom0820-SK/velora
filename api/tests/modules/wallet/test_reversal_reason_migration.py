"""T-8.2's two ledger reasons (D-521): migration e9a09934aeb7 rebuilds
`ledger_reason_t` with `purchase_reversal` and `purchase_restored`, and
fb0a7ce8dd16 names them in the ledger's shape. Both ways, keeping every other
reason, CHECK and index as it stood; and the way down refused once the ledger
holds either, since the ledger keeps every row (T-1.12).

As in test_reason_migration.py, the round trip in test_migrations.py can't see
a downgrade that leaves the values behind, so this goes down to the revision
before and reads the type and the shape back.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command
from app.core.enums import Gender, LedgerReason
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType
from tests.conftest import MakeUser
from tests.infra import run_alembic
from tests.modules.wallet.test_reason_migration import _alembic, _labels, _read

BEFORE = "b4bfd6974ee4"  # T-9.6's data exports, the head before T-8.2
RETYPE = "e9a09934aeb7"  # the two reasons
SHAPE = "fb0a7ce8dd16"  # the ledger's shape names them
ADDED = ["purchase_reversal", "purchase_restored"]


async def test_the_reasons_go_down_and_up_and_keep_what_stood(
    test_engine: AsyncEngine,
) -> None:
    try:
        head = await _read(test_engine)
        await run_alembic(test_engine, command.downgrade, BEFORE)
        before = await _read(test_engine)
        await run_alembic(test_engine, command.upgrade, RETYPE)
        retyped = await _read(test_engine)
        await run_alembic(test_engine, command.upgrade, SHAPE)
        shaped = await _read(test_engine)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")
    after = await _read(test_engine)

    assert retyped[0] == [*before[0], *ADDED]
    assert not set(ADDED) & set(before[0])
    # The rebuild re-created every CHECK and index exactly as it stood.
    assert retyped[1] == before[1]
    # The shape changes exactly its three rules, each naming both reasons.
    changed = {name for name in shaped[1] if shaped[1][name] != before[1][name]}
    assert changed == {
        "ck_ledger_entries_reason_direction",
        "ck_ledger_entries_reason_ref_type",
        "uq_ledger_entries_one_per_event",
    }
    for name in changed:
        assert all(reason in shaped[1][name] for reason in ADDED), name
    assert after == head


async def _reversal(db: AsyncSession, make_user: MakeUser) -> None:
    man, _ = await make_user(Gender.MALE, credits=10)
    await wallet_service.reverse(
        db,
        man.id,
        10,
        LedgerReason.PURCHASE_REVERSAL,
        ref=Ref(RefType.PAYMENT, uuid.uuid4()),
        event="rfnd_migration",
    )


async def test_the_reasons_refuse_to_go_down_once_the_ledger_holds_one(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """To reach the rebuild's own refusal, the shape that would refuse first
    (next test) is taken away and the database stamped back past it."""
    await _reversal(db, make_user)
    await db.execute(
        text(
            "alter table ledger_entries "
            "drop constraint ck_ledger_entries_reason_direction, "
            "drop constraint ck_ledger_entries_reason_ref_type"
        )
    )
    await db.execute(text("drop index uq_ledger_entries_one_per_event"))
    await _alembic(db, command.stamp, RETYPE)

    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert str(refused.value) == (
        "1 ledger entries use purchase_reversal or purchase_restored, and the "
        "ledger keeps every row (T-1.12), so they can't leave ledger_reason_t "
        "(D-521)"
    )
    # Still in the type, wherever a later task's reasons put them (T-8.11's
    # `welcome` comes after).
    labels = await _labels(await db.connection())
    assert [label for label in labels if label in ADDED] == ADDED


async def test_with_the_shape_in_place_its_check_refuses_first(
    db: AsyncSession, make_user: MakeUser
) -> None:
    await _reversal(db, make_user)

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert "ck_ledger_entries_reason_direction" in str(refused.value)
