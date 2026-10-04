"""gifts free fifteen a week

Revision ID: b270d197e38a
Revises: 0cbb8f2bc7c8
Create Date: 2026-10-04 23:10:14.424542

`app_config` (D-231, T-5.2): fifteen gift sends a week are free, and the
sixteenth costs its price. `gift_free_weekly_limit` (15) replaces
`gift_free_daily_limit` (D-016's 3 a day), which nothing reads yet: T-8.9 builds
gift sending, and says where the week starts. They are free sends, not a grant
of Velas: a free send moves no Vela and writes no ledger row (D-231).

The new key is inserted as T-1.14's were, ON CONFLICT DO NOTHING. The downgrade
removes it and puts D-016's daily key back at 3.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b270d197e38a"
down_revision: str | Sequence[str] | None = "0cbb8f2bc7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WEEKLY = ("gift_free_weekly_limit", 15)
DAILY = ("gift_free_daily_limit", 3)

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def _swap(old: tuple[str, int], new: tuple[str, int]) -> None:
    op.execute(sa.delete(app_config).where(app_config.c.key == old[0]))
    op.execute(
        postgresql.insert(app_config)
        .values(key=new[0], value=new[1])
        .on_conflict_do_nothing()
    )


def upgrade() -> None:
    """Upgrade schema."""
    _swap(DAILY, WEEKLY)


def downgrade() -> None:
    """Downgrade schema: D-016's daily limit."""
    _swap(WEEKLY, DAILY)
