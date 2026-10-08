"""a face photo for the selfie check

Revision ID: ed3028467a15
Revises: 15a9b138750b
Create Date: 2026-10-08 02:08:58.660219

`photo_kind_t` gains `verification` (D-391, T-4.12): the one photo whose job is
the selfie check, private unless its owner chooses to show it, compared with
the selfie alone. An identifier only: in copy it is "face photo" (D-262).

**The type is rebuilt, never given `ALTER TYPE ... ADD VALUE`,** as
`4a7e20790605` rebuilt `ledger_reason_t`, for its two reasons: Postgres can add
a value to an enum and never remove one, so the downgrade has to rebuild the
type whatever the upgrade does; and a value added by ADD VALUE can't be used in
the transaction that added it, which Alembic runs a whole upgrade in (env.py).

So both ways do the same thing, `_retype()`: build the type with the new list
under a temporary name, move `photos.kind` onto it, drop the old type and take
its name. The CHECK and the indexes on `photos` that read `kind`
(`ck_photos_public_position_range`, `ix_photos_user_id_kind_position`, and
`uq_photos_public_position`, whose predicate names it) are dropped first and
re-created after from their own definitions as the database holds them, so
whatever stood before stands after, weakened or not. The value lists are read
from the database rather than written out, so this migration adds exactly one
value to whatever the type holds.

**The downgrade refuses while any photo has the kind:** a face photo is a
person's, kept as every photo row is (rule 12), and the type can't lose a value
a row uses.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ed3028467a15"
down_revision: str | Sequence[str] | None = "15a9b138750b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPE = "photo_kind_t"
TABLE = "photos"
COLUMN = "kind"
ADDED = "verification"


def _labels() -> list[str]:
    """The type's values, in order. Found by name in a join, never by a
    `'photo_kind_t'::regtype` literal: that is fixed to an OID when the
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
    """`photos.kind` onto a `photo_kind_t` of exactly `labels`.

    The table is found by `to_regclass()`, run each time, never a
    `'photos'::regclass` literal, for `_labels()`'s reason: a table dropped and
    made again (the round trip to base) has a new OID."""
    bind = op.get_bind()
    checks = bind.execute(
        sa.text(
            "select c.conname, pg_get_constraintdef(c.oid) from pg_constraint c "
            "join pg_attribute a on a.attrelid = c.conrelid and a.attname = :column "
            "where c.conrelid = to_regclass(:table) and c.contype = 'c' "
            "and a.attnum = any (c.conkey) order by c.conname"
        ),
        {"table": TABLE, "column": COLUMN},
    ).all()
    # Every index that depends on the column: in its key, or in its predicate
    # (`uq_photos_public_position` reads `kind` only in its WHERE).
    indexes = bind.execute(
        sa.text(
            "select distinct i.relname, pg_get_indexdef(i.oid) from pg_index x "
            "join pg_class i on i.oid = x.indexrelid "
            "join pg_depend d on d.classid = 'pg_class'::regclass "
            "and d.objid = x.indexrelid and d.refclassid = 'pg_class'::regclass "
            "and d.refobjid = x.indrelid "
            "join pg_attribute a on a.attrelid = x.indrelid "
            "and a.attnum = d.refobjsubid and a.attname = :column "
            "where x.indrelid = to_regclass(:table) order by i.relname"
        ),
        {"table": TABLE, "column": COLUMN},
    ).all()

    for name, _ in checks:
        op.execute(f'ALTER TABLE {TABLE} DROP CONSTRAINT "{name}"')
    for name, _ in indexes:
        op.execute(f'DROP INDEX "{name}"')
    listed = ", ".join(f"'{label}'" for label in labels)
    op.execute(f"CREATE TYPE {TYPE}__next AS ENUM ({listed})")
    op.execute(
        f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} TYPE {TYPE}__next "
        f"USING {COLUMN}::text::{TYPE}__next"
    )
    op.execute(f"DROP TYPE {TYPE}")
    op.execute(f"ALTER TYPE {TYPE}__next RENAME TO {TYPE}")
    # The definitions name `photo_kind_t`, which is now the new type.
    for _, definition in indexes:
        op.execute(definition)
    for name, definition in checks:
        op.execute(f'ALTER TABLE {TABLE} ADD CONSTRAINT "{name}" {definition}')


def upgrade() -> None:
    """Upgrade schema."""
    labels = _labels()
    if ADDED in labels:
        raise RuntimeError(f"{TYPE} already has {ADDED}")
    _retype([*labels, ADDED])


def downgrade() -> None:
    """Downgrade schema: refused while any photo has the kind."""
    used = op.get_bind().scalar(
        sa.text(f"select count(*) from {TABLE} where {COLUMN}::text = :added"),
        {"added": ADDED},
    )
    if used:
        raise RuntimeError(
            f"{used} photos are face photos (kind {ADDED}), and a photo row is "
            f"never dropped (rule 12), so the value can't leave {TYPE} (D-391)"
        )
    _retype([label for label in _labels() if label != ADDED])
