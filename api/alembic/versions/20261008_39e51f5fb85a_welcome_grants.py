"""welcome grants

Revision ID: 39e51f5fb85a
Revises: a7e4f06d6b3f
Create Date: 2026-10-08 20:00:02.000000

`welcome_grants` (T-8.11, D-470, P-371): the hash of every phone number that
received welcome Velas, the HMAC `users.phone_hash` holds (D-061), so a number
gets them once, ever. The grant claims the number here before it credits, in
one statement (`INSERT ... ON CONFLICT DO NOTHING`), and a later account on the
same number, after T-9.6 has erased the first, finds it claimed.

`user_id` names the account that received the grant, RESTRICT like every key
into `users`: the erasure keeps it (D-503's KEPT) and an under-18 refusal can't
meet one, since the grant comes after `dob` (D-078, UNDERAGE_KEEPS). Unique, so
one account holds at most one, and the key's own check is an index lookup.

**Append-only.** T-1.12's `refuse_change()` refuses UPDATE, DELETE and
TRUNCATE, and the app role loses UPDATE and DELETE (`tests/test_app_role.py`
fails for a guarded privilege it keeps). A hash deleted would grant that number
again.

**The downgrade refuses while the table holds a row,** for the same reason:
dropping it forgets which numbers have had their welcome.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39e51f5fb85a"
down_revision: str | Sequence[str] | None = "a7e4f06d6b3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "velora_app"
GUARDS = (
    # (trigger name, timing and events, level)
    ("welcome_grants_no_update_delete", "before update or delete", "row"),
    ("welcome_grants_no_truncate", "before truncate", "statement"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "welcome_grants",
        sa.Column("phone_hash", sa.Text(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_welcome_grants_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("phone_hash", name=op.f("pk_welcome_grants")),
        sa.UniqueConstraint("user_id", name=op.f("uq_welcome_grants_user_id")),
    )
    for name, when, level in GUARDS:
        op.execute(
            sa.text(
                f"create trigger {name} {when} on welcome_grants "
                f"for each {level} execute function refuse_change()"
            )
        )
    op.execute(sa.text(f"revoke update, delete on welcome_grants from {APP_ROLE}"))


def downgrade() -> None:
    """Downgrade schema: refused while any number's grant is recorded."""
    held = op.get_bind().scalar(sa.text("select count(*) from welcome_grants"))
    if held:
        raise RuntimeError(
            f"welcome_grants holds {held} numbers that received welcome Velas; "
            "dropping it would grant each again (D-470, P-371)"
        )
    op.drop_table("welcome_grants")
