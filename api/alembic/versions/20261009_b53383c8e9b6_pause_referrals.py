"""pause referrals

Revision ID: b53383c8e9b6
Revises: 7ee6438868ed
Create Date: 2026-10-09 01:34:34.296215

P-740, D-840: referrals paused, `app_config.referral_reward_velas` set to 0. A
reward then pays nothing (D-692), and `POST /referrals/apply` is refused while
it isn't above 0, so no number spends its one referee slot (D-691) on a
referral that pays nothing. `tests/test_reference_data.py` holds the migrated
database to 0. The downgrade puts back T-8.6's 5. A missing row is left
missing either way: apply stays refused, and the reward is skipped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b53383c8e9b6"
down_revision: str | Sequence[str] | None = "7ee6438868ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY = "referral_reward_velas"
PAUSED, RUNNING = 0, 5

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def _set(value: int) -> None:
    op.execute(sa.update(app_config).where(app_config.c.key == KEY).values(value=value))


def upgrade() -> None:
    """Upgrade schema."""
    _set(PAUSED)


def downgrade() -> None:
    """Downgrade schema."""
    _set(RUNNING)
