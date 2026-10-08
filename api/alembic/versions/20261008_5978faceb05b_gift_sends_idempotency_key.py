"""gift sends idempotency key

Revision ID: 5978faceb05b
Revises: 959e7af5110e
Create Date: 2026-10-08 23:00:00.000000

T-8.9: `POST /gifts/send` takes an `Idempotency-Key`, and a send has to be
found again by it, so the key is kept on the send: one per sender, as an
order's is per user (T-8.1, D-481). The ledger's own key, built from the
send's id, is still what stops a double charge (02-ARCHITECTURE §3).

No `gift_sends` row existed anywhere when this was written, but the upgrade
doesn't rely on that: a row from before gets its own id as its key, so the
column is NOT NULL in any state and a downgrade, then an upgrade, still works.
The downgrade drops only the column; every send stays (rule 12).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5978faceb05b"
down_revision: str | Sequence[str] | None = "959e7af5110e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("gift_sends", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.execute("UPDATE gift_sends SET idempotency_key = id::text")
    op.alter_column("gift_sends", "idempotency_key", nullable=False)
    op.create_unique_constraint(
        "uq_gift_sends_sender_id_idempotency_key",
        "gift_sends",
        ["sender_id", "idempotency_key"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_gift_sends_sender_id_idempotency_key", "gift_sends", type_="unique"
    )
    op.drop_column("gift_sends", "idempotency_key")
