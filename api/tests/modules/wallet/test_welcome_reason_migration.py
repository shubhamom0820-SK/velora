"""T-8.11's ledger reason (D-470): migration acfda05a9f20 rebuilds
`ledger_reason_t` with `welcome`, a7e4f06d6b3f names it in the ledger's shape,
39e51f5fb85a makes `welcome_grants` and 105ae9a99be1 seeds `welcome_velas`.
Both ways, keeping every other reason, CHECK and index as it stood; the
reason's way down refused once the ledger holds one, since the ledger keeps
every row (T-1.12); and the table's refused while it holds a number, since
dropping it would grant each number again (P-371).

As in test_reason_migration.py, the round trip in test_migrations.py can't see
a downgrade that leaves the value behind, so this goes down to the revision
before and reads the type and the shape back.
"""

from __future__ import annotations

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

BEFORE = "386bbc188276"  # T-7.1's women's limits, the head before T-8.11
RETYPE = "acfda05a9f20"  # the reason
SHAPE = "a7e4f06d6b3f"  # the ledger's shape names it
GRANTS = "39e51f5fb85a"  # welcome_grants
ADDED = ["welcome"]


async def _table_and_setting(engine: AsyncEngine) -> tuple[bool, object]:
    async with engine.connect() as connection:
        table = await connection.scalar(
            text("select to_regclass('welcome_grants') is not null")
        )
        setting = await connection.scalar(
            text("select value from app_config where key = 'welcome_velas'")
        )
    return bool(table), setting


async def test_the_reason_goes_down_and_up_and_keeps_what_stood(
    test_engine: AsyncEngine,
) -> None:
    try:
        head = await _read(test_engine)
        at_head = await _table_and_setting(test_engine)
        await run_alembic(test_engine, command.downgrade, BEFORE)
        before = await _read(test_engine)
        at_before = await _table_and_setting(test_engine)
        await run_alembic(test_engine, command.upgrade, RETYPE)
        retyped = await _read(test_engine)
        await run_alembic(test_engine, command.upgrade, SHAPE)
        shaped = await _read(test_engine)
    finally:
        await run_alembic(test_engine, command.upgrade, "head")
    after = await _read(test_engine)

    assert at_head == (True, 5)
    assert at_before == (False, None)
    # Every reason T-8.2 left, its two included, and `welcome` after them.
    assert retyped[0] == [*before[0], *ADDED]
    assert before[0][-2:] == ["purchase_reversal", "purchase_restored"]
    # The rebuild re-created every CHECK and index exactly as it stood.
    assert retyped[1] == before[1]
    # The shape changes exactly its two CHECKs, each naming `welcome`; the
    # per-event index lists only the reasons that repeat, so it stands as it
    # was, and `welcome` is inside it.
    changed = {name for name in shaped[1] if shaped[1][name] != before[1][name]}
    assert changed == {
        "ck_ledger_entries_reason_direction",
        "ck_ledger_entries_reason_ref_type",
    }
    for name in changed:
        assert "'welcome'" in shaped[1][name], name
    assert "welcome" not in shaped[1]["uq_ledger_entries_one_per_event"]
    assert after == head


async def _welcome(db: AsyncSession, make_user: MakeUser) -> None:
    man, _ = await make_user(Gender.MALE)
    await wallet_service.credit(
        db, man.id, 5, LedgerReason.WELCOME, ref=Ref(RefType.USER, man.id)
    )


async def test_the_reason_refuses_to_go_down_once_the_ledger_holds_one(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """To reach the rebuild's own refusal, the shape that would refuse first
    (next test) is taken away and the database stamped back past it."""
    await _welcome(db, make_user)
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
        "1 ledger entries use welcome, and the ledger keeps every row (T-1.12), "
        "so it can't leave ledger_reason_t (D-470)"
    )
    labels = await _labels(await db.connection())
    assert [label for label in labels if label in ADDED] == ADDED


async def test_with_the_shape_in_place_its_check_refuses_first(
    db: AsyncSession, make_user: MakeUser
) -> None:
    await _welcome(db, make_user)

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE)

    assert "ck_ledger_entries_reason_direction" in str(refused.value)


async def test_the_table_refuses_to_go_down_while_it_holds_a_number(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user(Gender.MALE)
    await db.execute(
        text("insert into welcome_grants (phone_hash, user_id) values (:h, :u)"),
        {"h": man.phone_hash, "u": man.id},
    )

    with pytest.raises(RuntimeError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, SHAPE)

    assert str(refused.value) == (
        "welcome_grants holds 1 numbers that received welcome Velas; dropping it "
        "would grant each again (D-470, P-371)"
    )
    assert await db.scalar(text("select count(*) from welcome_grants")) == 1
