"""one order per idempotency key

Revision ID: 25558532ccde
Revises: 86d605e7b904
Create Date: 2026-10-08 12:00:01.000000

`payments.idempotency_key` (D-481, T-8.1): the client's `Idempotency-Key` for
`POST /payments/orders`, unique per user, so a key sent twice, at once or a day
apart, is one order. Postgres holds it, not Redis: a store that expires or is
flushed would let a retried click open a second order (02-ARCHITECTURE §3).

NOT NULL, with no default: no route wrote `payments` before this task, so the
table is empty wherever this runs. If it isn't, the upgrade fails rather than
inventing keys for orders nobody sent one with.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25558532ccde"
down_revision: str | Sequence[str] | None = "86d605e7b904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("payments", sa.Column("idempotency_key", sa.Text(), nullable=False))
    op.create_unique_constraint(
        op.f("uq_payments_user_id_idempotency_key"),
        "payments",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("uq_payments_user_id_idempotency_key"), "payments", type_="unique"
    )
    op.drop_column("payments", "idempotency_key")
