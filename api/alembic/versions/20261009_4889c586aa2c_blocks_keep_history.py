"""blocks keep history

Revision ID: 4889c586aa2c
Revises: bb4531b1f569
Create Date: 2026-10-09 05:10:00.000000

`blocks` (T-9.1, D-860, P-16): unblocking keeps the row. Each block gets an
`id` and an `unblocked_at`, and the pair's primary key becomes a partial
unique index, `uq_blocks_active`: one standing block per pair, and as many
lifted ones as there have been. Blocking again after an unblock is a new row.
"Blocked by many people" stays a fraud and moderation signal.

The index leads with `blocker_id`, so it also serves every "does a block
stand" read (`blocked_either_way`), which only ever asks about standing ones.

**The downgrade refuses while any lifted block is recorded**: the old primary
key holds one row per pair, so going back would have to delete history that
moderation may need (rule 12's principle).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4889c586aa2c"
down_revision: str | Sequence[str] | None = "bb4531b1f569"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "blocks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )
    op.add_column(
        "blocks", sa.Column("unblocked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_constraint("pk_blocks", "blocks", type_="primary")
    op.create_primary_key("pk_blocks", "blocks", ["id"])
    op.create_index(
        "uq_blocks_active",
        "blocks",
        ["blocker_id", "blocked_id"],
        unique=True,
        postgresql_where=sa.text("unblocked_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema: refused while any lifted block is recorded."""
    lifted = op.get_bind().scalar(
        sa.text("select count(*) from blocks where unblocked_at is not null")
    )
    if lifted:
        raise RuntimeError(
            f"{lifted} lifted blocks are recorded, and the old primary key holds "
            "one row per pair: going back would delete their history (D-860)"
        )
    op.drop_index("uq_blocks_active", table_name="blocks")
    op.drop_constraint("pk_blocks", "blocks", type_="primary")
    op.create_primary_key("pk_blocks", "blocks", ["blocker_id", "blocked_id"])
    op.drop_column("blocks", "unblocked_at")
    op.drop_column("blocks", "id")
