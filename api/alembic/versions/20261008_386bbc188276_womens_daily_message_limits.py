"""women's daily message limits

Revision ID: 386bbc188276
Revises: ddf84381ef6c
Create Date: 2026-10-08 22:00:01.000000

D-098's two rate limits for a woman, by the IST day (T-7.1, T-7.3; the
founder, 8 October 2026), as `app_config` values:

- `women_new_men_daily_limit` 30: different men she opens a Thread with or
  writes to first;
- `women_private_messages_daily_limit` 30: her messages in private-message
  Threads.

Limits, never prices: she is never charged (D-098). Inserted as T-1.14's keys
were, ON CONFLICT DO NOTHING. The downgrade removes them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "386bbc188276"
down_revision: str | Sequence[str] | None = "ddf84381ef6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIMITS = {
    "women_new_men_daily_limit": 30,
    "women_private_messages_daily_limit": 30,
}

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        postgresql.insert(app_config)
        .values([{"key": key, "value": value} for key, value in LIMITS.items()])
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.delete(app_config).where(app_config.c.key.in_(list(LIMITS))))
