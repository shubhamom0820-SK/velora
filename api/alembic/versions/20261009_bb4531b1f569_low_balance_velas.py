"""low balance velas

Revision ID: bb4531b1f569
Revises: 84301f562b60
Create Date: 2026-10-09 12:00:02.000000

`app_config` (T-9.4, D-853): a debit that takes a man's balance from
`low_balance_velas` or more to below it sends him one `low_balance`
notification. 10, one Extend (the founder, 9 October 2026). Read fresh at
each debit, so a changed value applies at once.

Inserted as T-1.14's keys were, ON CONFLICT DO NOTHING, so a tuned value
survives a re-run. The downgrade removes exactly this key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb4531b1f569"
down_revision: str | Sequence[str] | None = "84301f562b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY, VELAS = "low_balance_velas", 10

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        postgresql.insert(app_config)
        .values(key=KEY, value=VELAS)
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.delete(app_config).where(app_config.c.key == KEY))
