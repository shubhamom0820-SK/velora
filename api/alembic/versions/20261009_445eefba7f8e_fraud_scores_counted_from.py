"""fraud scores counted from

Revision ID: 445eefba7f8e
Revises: 4800f0e8d5a9
Create Date: 2026-10-09 18:00:01.000000

`fraud_scores.counted_from` (T-9.2, D-906): when the founder lifts a freeze
(`python -m app.tools.unfreeze`), the score starts again from that moment.
Signals and reports from before it no longer count, so the next recompute
can't freeze the account again on the evidence a person has just looked at
and set aside. The events themselves stay: they are moderation's record.
Null: everything counts, as before.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "445eefba7f8e"
down_revision: str | Sequence[str] | None = "4800f0e8d5a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "fraud_scores",
        sa.Column("counted_from", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("fraud_scores", "counted_from")
