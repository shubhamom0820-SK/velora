"""gst rate bps

Revision ID: 300945192d27
Revises: 25558532ccde
Create Date: 2026-10-08 12:00:02.000000

`app_config.gst_rate_bps` (D-450, D-482, T-8.1): 1800, 18% in basis points, the
rate on digital services as the founder relayed it from a chartered accountant.
Nothing reads it while Velora is unregistered: the API refuses
`GST_REGISTERED=true` until P-350's task builds the split that uses it.

Inserted as T-1.14's keys were, ON CONFLICT DO NOTHING. The downgrade removes it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "300945192d27"
down_revision: str | Sequence[str] | None = "25558532ccde"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GST_RATE_BPS = ("gst_rate_bps", 1800)

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def upgrade() -> None:
    """Upgrade schema."""
    key, value = GST_RATE_BPS
    op.execute(
        postgresql.insert(app_config)
        .values(key=key, value=value)
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.delete(app_config).where(app_config.c.key == GST_RATE_BPS[0]))
