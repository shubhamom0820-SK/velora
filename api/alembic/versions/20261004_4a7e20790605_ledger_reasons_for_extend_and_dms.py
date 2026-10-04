"""ledger reasons for extend and private messages

Revision ID: 4a7e20790605
Revises: 190d7bebf133
Create Date: 2026-10-04 23:10:12.809155

`ledger_reason_t` gains `thread_extend` and `dm_message` (D-251, T-5.2): D-098's
two new priced actions, Extend and each private message after the first, each a
debit reason of its own. Nothing can write either until the next migration
names them in D-077's shape, since the direction CHECK is an allowlist.

**The type is rebuilt, not given `ALTER TYPE ... ADD VALUE`,** for two reasons:
- Postgres can add a value to an enum and never remove one, so the downgrade
  has to rebuild the type whatever the upgrade does.
- A value added by ADD VALUE can't be used in the transaction that added it.
  Alembic runs a whole upgrade in one transaction (env.py), so the next
  migration's CHECKs couldn't name it without `autocommit_block()`, which gives
  up that atomicity and fails under the tests' `run_alembic`, whose connection
  is already in a transaction.

So both ways do the same thing, `_retype()`: build the type with the new list
under a temporary name, move `ledger_entries.reason` onto it, drop the old type
and take its name. The CHECKs and indexes that read `reason` are dropped first
and re-created after from their own definitions as the database holds them, so
whatever stood before stands after, weakened or not. Rewriting the table fires
none of the ledger's triggers: they guard rows and TRUNCATE, not ALTER TABLE.

**The downgrade refuses while any ledger row uses either value.** The ledger
refuses DELETE (T-1.12), so such a row is permanent, and from then on so is
this migration. The value lists are read from the database rather than written
out, so this migration adds exactly two values to whatever the type holds.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a7e20790605"
down_revision: str | Sequence[str] | None = "190d7bebf133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPE = "ledger_reason_t"
ADDED = ("thread_extend", "dm_message")


def _labels() -> list[str]:
    """The type's values, in order. Found by name in a join, never by a
    `'ledger_reason_t'::regtype` literal: that is fixed to an OID when the
    statement is prepared, and asyncpg keeps prepared statements per
    connection, so after one rebuild the same text would read the dropped
    type's values, none, on any connection that ran it before."""
    return list(
        op.get_bind().scalars(
            sa.text(
                "select e.enumlabel from pg_enum e "
                "join pg_type t on t.oid = e.enumtypid "
                "where t.typname = :name and pg_type_is_visible(t.oid) "
                "order by e.enumsortorder"
            ),
            {"name": TYPE},
        )
    )


def _retype(labels: list[str]) -> None:
    """`ledger_entries.reason` onto a `ledger_reason_t` of exactly `labels`.

    The table is found by `to_regclass()`, run each time, never a
    `'ledger_entries'::regclass` literal, for `_labels()`'s reason: a table
    dropped and made again (the round trip to base) has a new OID."""
    bind = op.get_bind()
    checks = bind.execute(
        sa.text(
            "select c.conname, pg_get_constraintdef(c.oid) from pg_constraint c "
            "join pg_attribute a on a.attrelid = c.conrelid and a.attname = 'reason' "
            "where c.conrelid = to_regclass('ledger_entries') and c.contype = 'c' "
            "and a.attnum = any (c.conkey) order by c.conname"
        )
    ).all()
    indexes = bind.execute(
        sa.text(
            "select distinct i.relname, pg_get_indexdef(i.oid) from pg_index x "
            "join pg_class i on i.oid = x.indexrelid "
            "join pg_depend d on d.classid = 'pg_class'::regclass "
            "and d.objid = x.indexrelid and d.refclassid = 'pg_class'::regclass "
            "and d.refobjid = x.indrelid "
            "join pg_attribute a on a.attrelid = x.indrelid "
            "and a.attnum = d.refobjsubid and a.attname = 'reason' "
            "where x.indrelid = to_regclass('ledger_entries') order by i.relname"
        )
    ).all()

    for name, _ in checks:
        op.execute(f'ALTER TABLE ledger_entries DROP CONSTRAINT "{name}"')
    for name, _ in indexes:
        op.execute(f'DROP INDEX "{name}"')
    listed = ", ".join(f"'{label}'" for label in labels)
    op.execute(f"CREATE TYPE {TYPE}__next AS ENUM ({listed})")
    op.execute(
        f"ALTER TABLE ledger_entries ALTER COLUMN reason TYPE {TYPE}__next "
        f"USING reason::text::{TYPE}__next"
    )
    op.execute(f"DROP TYPE {TYPE}")
    op.execute(f"ALTER TYPE {TYPE}__next RENAME TO {TYPE}")
    # The definitions name `ledger_reason_t`, which is now the new type.
    for _, definition in indexes:
        op.execute(definition)
    for name, definition in checks:
        op.execute(f'ALTER TABLE ledger_entries ADD CONSTRAINT "{name}" {definition}')


def upgrade() -> None:
    """Upgrade schema."""
    labels = _labels()
    if present := [label for label in ADDED if label in labels]:
        raise RuntimeError(f"{TYPE} already has {', '.join(present)}")
    _retype([*labels, *ADDED])


def downgrade() -> None:
    """Downgrade schema: refused once the ledger holds either reason."""
    used = op.get_bind().scalar(
        sa.text("select count(*) from ledger_entries where reason::text = any(:added)"),
        {"added": list(ADDED)},
    )
    if used:
        raise RuntimeError(
            f"{used} ledger entries use thread_extend or dm_message, and the ledger "
            "keeps every row (T-1.12), so they can't leave ledger_reason_t (D-251)"
        )
    _retype([label for label in _labels() if label not in ADDED])
