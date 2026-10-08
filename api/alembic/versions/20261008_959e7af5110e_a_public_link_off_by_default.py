"""a public link, off by default

Revision ID: 959e7af5110e
Revises: 02f42ccb4d88
Create Date: 2026-10-08 20:00:00.000000

`profiles.public_link` (T-6.8, D-544): whether `/@username` shows anything to
someone not signed in. **Off for everyone, those already here included**: a
woman's photo, first name, age and city reach the open internet only when she
turns it on (the founder, 8 October 2026). The in-app profile doesn't read it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "959e7af5110e"
down_revision: str | Sequence[str] | None = "02f42ccb4d88"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "public_link", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "public_link")
