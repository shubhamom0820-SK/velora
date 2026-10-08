"""data exports

Revision ID: b4bfd6974ee4
Revises: a3c12afe34d5
Create Date: 2026-10-08 12:10:00.000000

`data_exports` (T-9.6, D-502): one row per copy of their data a user asks for.
The worker writes the file to the private bucket; the API signs a link to it
until `expires_at`, 24 hours after it was ready; then the file is deleted and
the row says `expired`. Rows only, so a plain table with the app role's default
grants: an under-18 refusal (D-078) and the erasure (D-500) delete its rows.

**The downgrade refuses while any export may still have its file**, since the
row is the only record of where a phone number's copy is stored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4bfd6974ee4"
down_revision: str | Sequence[str] | None = "a3c12afe34d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "data_exports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("file_key", sa.Text(), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'expired')",
            name=op.f("ck_data_exports_status_known"),
        ),
        sa.CheckConstraint(
            "status <> 'ready' OR (file_key IS NOT NULL AND ready_at IS NOT NULL "
            "AND expires_at IS NOT NULL)",
            name=op.f("ck_data_exports_ready_has_a_file"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_data_exports_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_exports")),
    )
    op.create_index(
        "ix_data_exports_user_id_created_at",
        "data_exports",
        ["user_id", sa.text("created_at DESC")],
    )
    op.execute(
        sa.text(
            "create trigger trg_data_exports_updated_at before update on data_exports "
            "for each row execute function set_updated_at()"
        )
    )


def downgrade() -> None:
    """Downgrade schema: refused while an export's file may still be stored,
    which dropping its row would leave with nothing pointing at it."""
    stored = op.get_bind().scalar(
        sa.text("select count(*) from data_exports where file_key is not null")
    )
    if stored:
        raise RuntimeError(
            f"{stored} data exports may still have a file in the private bucket, "
            "each holding a phone number: let them expire first (D-502)"
        )
    op.drop_index("ix_data_exports_user_id_created_at", table_name="data_exports")
    op.drop_table("data_exports")
