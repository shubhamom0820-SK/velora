"""reports reporter index

Revision ID: 086fa0402d0d
Revises: 4889c586aa2c
Create Date: 2026-10-09 10:31:33.336418

`GET /reports` (T-9.8, D-911) lists the reports a person filed, newest first:
an index on `(reporter_id, created_at DESC)`, as `reported_id` has one for
moderation's reads. No rows change, so the downgrade only drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "086fa0402d0d"
down_revision: str | Sequence[str] | None = "4889c586aa2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX = "ix_reports_reporter_id_created_at"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        INDEX,
        "reports",
        ["reporter_id", sa.literal_column("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX, table_name="reports")
