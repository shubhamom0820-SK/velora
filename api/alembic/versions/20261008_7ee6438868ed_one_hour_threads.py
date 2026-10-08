"""one hour threads

Revision ID: 7ee6438868ed
Revises: 0e6719809c1b
Create Date: 2026-10-08 23:00:00.000000

The 1-hour Thread (T-7.6, D-097, D-560): `app_config.thread_hours` goes from
24 to 1, and two settings join it, `thread_extend_hours` (24, what Extend buys)
and `thread_warn_minutes` (10, when he is warned). Copy promises
`thread_hours` (03-SCHEMA §8), so the landing page, `/terms`, the match sheet
and the share image change in the same commit.

The new keys are inserted as T-1.14's were, ON CONFLICT DO NOTHING. The
downgrade removes them and puts `thread_hours` back to 24.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ee6438868ed"
down_revision: str | Sequence[str] | None = "0e6719809c1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THREAD_HOURS = ("thread_hours", 1)
THREAD_HOURS_BEFORE = 24
NEW_KEYS = (("thread_extend_hours", 24), ("thread_warn_minutes", 10))

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def _set(key: str, value: int) -> None:
    op.execute(sa.update(app_config).where(app_config.c.key == key).values(value=value))


def upgrade() -> None:
    """Upgrade schema."""
    _set(*THREAD_HOURS)
    for key, value in NEW_KEYS:
        op.execute(
            postgresql.insert(app_config)
            .values(key=key, value=value)
            .on_conflict_do_nothing()
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.delete(app_config).where(app_config.c.key.in_([k for k, _ in NEW_KEYS]))
    )
    _set(THREAD_HOURS[0], THREAD_HOURS_BEFORE)
