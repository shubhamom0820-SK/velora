"""referral settings

Revision ID: 0e6719809c1b
Revises: 5978faceb05b
Create Date: 2026-10-08 22:00:00.000000

T-8.6's two settings (D-692): `app_config.referral_reward_velas`, 5, the Velas
each man on a referral is given when it is rewarded, tunable, 0 rewarding it
with nothing and a missing row skipping it with a warning; and
`referral_rewards_max`, 10, how many referrals one referrer is paid for, ever,
a missing row paying him nothing. `tests/test_reference_data.py` holds the
migrated database to both rows.

Inserted as T-1.14's keys were, ON CONFLICT DO NOTHING. The downgrade removes them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e6719809c1b"
down_revision: str | Sequence[str] | None = "5978faceb05b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SETTINGS = (("referral_reward_velas", 5), ("referral_rewards_max", 10))

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        postgresql.insert(app_config)
        .values([{"key": key, "value": value} for key, value in SETTINGS])
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.delete(app_config).where(app_config.c.key.in_([key for key, _ in SETTINGS]))
    )
