"""bans are lifted in place

Revision ID: 7c8a628fd3d7
Revises: 7a758777affd
Create Date: 2026-10-16 09:00:03.000000

**A ban is lifted, never deleted** (T-9.5, D-922; the founder on the advisor's
recommendation, relayed, 16 October 2026: golden rule 12, nothing moderation
may need is hard-deleted). An admin's unban keeps the `banned_identities` row
and records the lift on it: `lifted_at`, `lifted_by` and `lift_reason`, all
three or none (`ck_banned_identities_lift_complete`). Sign-in and the OTP send
read only standing rows, `lifted_at IS NULL`. Every lift is audited too.

**Only a ban is ever lifted.** `refuse_banned_identity_change()` refuses every
UPDATE but one: a standing row whose `reason` is `ban` getting its three lift
columns, nothing else changing. So an `underage` row (D-072) can never be
lifted, by the app or by anyone with the app's password, and a lift can't be
undone or rewritten. It refuses every DELETE, and T-1.12's `refuse_change()`
every TRUNCATE; both raise `restrict_violation` (23001), as the ledger's do.
The app role keeps INSERT and SELECT, loses DELETE, and may UPDATE only the
three lift columns.

**One standing row per number:** `uq_banned_identities_kind_value` becomes a
partial unique index on `(kind, value) WHERE lifted_at IS NULL`, so a number
banned again after a lift gets a row of its own, and the lifted one stays as
the record of what happened.

The downgrade refuses while any row has been lifted: the table before this
has nowhere to keep a lift, and a lifted row put back as standing would ban
that number again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c8a628fd3d7"
down_revision: str | Sequence[str] | None = "7a758777affd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "velora_app"
TABLE = "banned_identities"
LIFT_COLUMNS = "lifted_at, lifted_by, lift_reason"
STANDING = "uq_banned_identities_standing"
FUNCTION = "refuse_banned_identity_change"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(TABLE, sa.Column("lifted_at", sa.DateTime(timezone=True)))
    op.add_column(TABLE, sa.Column("lifted_by", postgresql.UUID(as_uuid=True)))
    op.add_column(TABLE, sa.Column("lift_reason", sa.Text()))
    op.create_foreign_key(
        op.f("fk_banned_identities_lifted_by_users"),
        TABLE,
        "users",
        ["lifted_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_banned_identities_lift_complete"),
        TABLE,
        "(lifted_at IS NULL) = (lifted_by IS NULL) "
        "AND (lifted_at IS NULL) = (lift_reason IS NULL)",
    )
    op.drop_constraint(op.f("uq_banned_identities_kind_value"), TABLE, type_="unique")
    op.create_index(
        STANDING,
        TABLE,
        ["kind", "value"],
        unique=True,
        postgresql_where=sa.text("lifted_at IS NULL"),
    )
    op.execute(
        sa.text(
            f"""
            create function {FUNCTION}() returns trigger
            language plpgsql as $$
            begin
                if tg_op = 'DELETE' then
                    raise exception 'banned_identities keeps every row: a ban is lifted, never deleted (D-922)'
                        using errcode = 'restrict_violation';
                end if;
                if old.lifted_at is not null then
                    raise exception 'a lifted ban never changes again (D-922)'
                        using errcode = 'restrict_violation';
                end if;
                if old.reason is distinct from 'ban' then
                    raise exception 'only a ban is ever lifted, never % (D-922)', coalesce(old.reason, 'no reason')
                        using errcode = 'restrict_violation';
                end if;
                if new.lifted_at is null
                    or new.id is distinct from old.id
                    or new.kind is distinct from old.kind
                    or new.value is distinct from old.value
                    or new.reason is distinct from old.reason
                    or new.created_at is distinct from old.created_at then
                    raise exception 'a ban changes only by being lifted (D-922)'
                        using errcode = 'restrict_violation';
                end if;
                return new;
            end
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"create trigger banned_identities_lift_only before update or delete "
            f"on {TABLE} for each row execute function {FUNCTION}()"
        )
    )
    op.execute(
        sa.text(
            f"create trigger banned_identities_no_truncate before truncate "
            f"on {TABLE} for each statement execute function refuse_change()"
        )
    )
    op.execute(sa.text(f"revoke update, delete on {TABLE} from {APP_ROLE}"))
    op.execute(sa.text(f"grant update ({LIFT_COLUMNS}) on {TABLE} to {APP_ROLE}"))


def downgrade() -> None:
    """Downgrade schema: refused once a ban has been lifted."""
    lifted = op.get_bind().scalar(
        sa.text(f"select count(*) from {TABLE} where lifted_at is not null")
    )
    if lifted:
        raise RuntimeError(
            f"{lifted} bans have been lifted, and the table before T-9.5 has "
            "nowhere to keep a lift: putting them back would ban those numbers "
            "again (D-922)"
        )
    op.execute(sa.text(f"revoke update ({LIFT_COLUMNS}) on {TABLE} from {APP_ROLE}"))
    op.execute(sa.text(f"grant update, delete on {TABLE} to {APP_ROLE}"))
    op.execute(sa.text(f"drop trigger banned_identities_no_truncate on {TABLE}"))
    op.execute(sa.text(f"drop trigger banned_identities_lift_only on {TABLE}"))
    op.execute(sa.text(f"drop function {FUNCTION}()"))
    op.drop_index(STANDING, table_name=TABLE)
    op.create_unique_constraint(
        op.f("uq_banned_identities_kind_value"), TABLE, ["kind", "value"]
    )
    op.drop_constraint(op.f("ck_banned_identities_lift_complete"), TABLE)
    op.drop_constraint(op.f("fk_banned_identities_lifted_by_users"), TABLE)
    op.drop_column(TABLE, "lift_reason")
    op.drop_column(TABLE, "lifted_by")
    op.drop_column(TABLE, "lifted_at")
