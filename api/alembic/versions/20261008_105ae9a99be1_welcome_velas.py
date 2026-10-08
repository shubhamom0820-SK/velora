"""welcome velas

Revision ID: 105ae9a99be1
Revises: 39e51f5fb85a
Create Date: 2026-10-08 20:00:03.000000

`app_config.welcome_velas` (T-8.11, D-470): 5, the Velas every new man is given
when he finishes sign-up, once per number. Tunable like the prices (D-005,
D-098): at 0 the service writes nothing. A missing row skips the grant with a
warning and never fails a sign-up (D-530), so `tests/test_reference_data.py`
holds the migrated database to this row.

Inserted as T-1.14's keys were, ON CONFLICT DO NOTHING. The downgrade removes it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "105ae9a99be1"
down_revision: str | Sequence[str] | None = "39e51f5fb85a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WELCOME_VELAS = ("welcome_velas", 5)

app_config = sa.table(
    "app_config", sa.column("key"), sa.column("value", postgresql.JSONB)
)


def upgrade() -> None:
    """Upgrade schema."""
    key, value = WELCOME_VELAS
    op.execute(
        postgresql.insert(app_config)
        .values(key=key, value=value)
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.delete(app_config).where(app_config.c.key == WELCOME_VELAS[0]))
