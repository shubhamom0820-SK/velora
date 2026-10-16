"""T-9.5's ledger migrations (D-923): eb2e5b3a5cc8 rebuilds `ledger_reason_t`
with `admin_correction`, 688032b1dc7a names it in the ledger's shape, and
7a758777affd makes every reason name its ref, `admin_grant` included, `NOT
VALID`. Both ways, keeping every other reason, CHECK and index as it stood; the
reason's way down refused once the ledger holds one, since the ledger keeps
every row (T-1.12).

As in test_reason_migration.py, the round trip in test_migrations.py can't see
a downgrade that leaves the value behind, so this goes down to the revision
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

BEFORE = "445eefba7f8e"  # T-9.2's counted_from, the head before T-9.5
RETYPE = "eb2e5b3a5cc8"  # the reason
SHAPE = "688032b1dc7a"  # the ledger's shape names it
REF_REQUIRED = "7a758777affd"  # every reason names its ref
ADDED = ["admin_correction"]
REF_RULE = "ck_ledger_entries_ref_required"


async def _validated(engine: AsyncEngine) -> bool:
    async with engine.connect() as connection:
        validated = await connection.scalar(
            text(
                "select convalidated from pg_constraint "
                "where conname = :name and conrelid = to_regclass('ledger_entries')"
            ),
            {"name": REF_RULE},
        )
    return bool(validated)


async def test_the_reason_goes_down_and_up_and_keeps_what_stood(
    test_engine: AsyncEngine,
) -> None:
    try:
        head = await _read(test_engine)
        head_validated = await _validated(test_engine)
        await run_alembic(test_engine, command.downgrade, BEFORE)
        before = await _read(test_engine)
        before_validated = await _validated(test_engine)
        await run_alembic(test_engine, command.upgrade, RETYPE)
        retyped = await _read(test_engine)
        await run_alembic(test_engine, command.upgrade, SHAPE)
        shaped = await _read(test_engine)
        await run_alembic(test_engine, command.upgrade, REF_REQUIRED)
        required = await _read(test_engine)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")
    after = await _read(test_engine)

    # Every reason that stood, `welcome` last, and `admin_correction` after it.
    assert retyped[0] == [*before[0], *ADDED]
    assert before[0][-1] == "welcome"
    # The rebuild re-created every CHECK and index exactly as it stood.
    assert retyped[1] == before[1]
    # The shape changes its two CHECKs and the per-event index, each naming
    # `admin_correction`: a debit, an audit row, and a reason that repeats.
    changed = {name for name in shaped[1] if shaped[1][name] != before[1][name]}
    assert changed == {
        "ck_ledger_entries_reason_direction",
        "ck_ledger_entries_reason_ref_type",
        "uq_ledger_entries_one_per_event",
    }
    for name in changed:
        assert "'admin_correction'" in shaped[1][name], name
    # Then only the ref rule changes, naming no reason, and is NOT VALID.
    changed = {name for name in required[1] if required[1][name] != shaped[1][name]}
    assert changed == {REF_RULE}
    assert before[1][REF_RULE] == (
        "CHECK (((reason = 'admin_grant'::ledger_reason_t) OR (ref_id IS NOT NULL)))"
    )
    assert required[1][REF_RULE] == "CHECK ((ref_id IS NOT NULL)) NOT VALID"
    assert (before_validated, head_validated) == (True, False)
    assert after == head


async def test_an_admin_grant_with_no_ref_is_refused_by_the_database(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(Gender.MALE)

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await db.execute(
                text(
                    "insert into ledger_entries (user_id, delta, balance_after, "
                    "reason, idempotency_key) values (:u, 5, 5, 'admin_grant', :k)"
                ),
                {"u": man.id, "k": f"guard-{uuid.uuid4()}"},
            )

    assert REF_RULE in str(refused.value)


async def _correction(db: AsyncSession, make_user: MakeUser) -> None:
    """A man given 5 and corrected by 2: the correction is a debit, which only
    the wallet's named callers may await, and tests (P-152)."""
    man, _ = await make_user(Gender.MALE, credits=5)
    await wallet_service.debit(
        db,
        man.id,
        2,
        LedgerReason.ADMIN_CORRECTION,
        ref=Ref(RefType.AUDIT_LOG, uuid.uuid4()),
        event="correction",
    )


async def test_the_reason_refuses_to_go_down_once_the_ledger_holds_one(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """To reach the rebuild's own refusal, the shape that would refuse first
    (next test) is taken away and the database stamped back past it."""
    await _correction(db, make_user)
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
        "1 ledger entries use admin_correction, and the ledger keeps every row "
        "(T-1.12), so it can't leave ledger_reason_t (D-923)"
    )
    labels = await _labels(await db.connection())
    assert [label for label in labels if label in ADDED] == ADDED


async def test_with_the_shape_in_place_its_check_refuses_first(
    db: AsyncSession, make_user: MakeUser
) -> None:
    await _correction(db, make_user)

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert "ck_ledger_entries_reason_direction" in str(refused.value)
