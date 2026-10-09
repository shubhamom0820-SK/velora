"""gift and album prefs

Revision ID: 18fc99762f2a
Revises: 652c4bad186e
Create Date: 2026-10-09 12:00:00.000000

`notification_prefs` (T-9.4, D-851): two more settings, `gift` (P-550) and
`album` (P-631: a request to see her album, and his answer back), each a
boolean, not null, true by default, as the five before them. Every existing
row takes the default, so nobody who had pushes on loses the new kinds.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "18fc99762f2a"
down_revision: str | Sequence[str] | None = "652c4bad186e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("gift", "album")


def upgrade() -> None:
    """Upgrade schema."""
    for name in COLUMNS:
        op.add_column(
            "notification_prefs",
            sa.Column(name, sa.Boolean(), server_default=sa.true(), nullable=False),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for name in reversed(COLUMNS):
        op.drop_column("notification_prefs", name)
