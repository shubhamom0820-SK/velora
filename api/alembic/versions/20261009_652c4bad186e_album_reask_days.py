"""album reask days

Revision ID: 652c4bad186e
Revises: 57ab54709630
Create Date: 2026-10-09 01:38:00.808313

`app_config` (T-8.4, D-731): after she declines or revokes a man's album
request, he can't ask her again for `album_reask_days`, 30. Read fresh at each
request, so a changed value applies at once.

Inserted as T-1.14's keys were, ON CONFLICT DO NOTHING, so a tuned value
survives a re-run. The downgrade removes exactly this key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "652c4bad186e"
down_revision: str | Sequence[str] | None = "57ab54709630"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY, DAYS = "album_reask_days", 30

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        postgresql.insert(app_config)
        .values(key=KEY, value=DAYS)
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.delete(app_config).where(app_config.c.key == KEY))
