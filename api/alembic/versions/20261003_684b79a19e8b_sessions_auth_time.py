"""sessions auth time

Revision ID: 684b79a19e8b
Revises: 89b155534dcf
Create Date: 2026-10-03 07:51:58.496249

`sessions.auth_time`: when the session's family signed in, by OTP or Firebase
(D-071). Every access token carries it, and a refresh (T-3.4) copies it from the
rotated session to the new one unchanged, so D-069's PIN reset can tell a fresh
sign-in without a database read per request.

On the row, not derived: the family's first session is rotated, so revoked,
and the only index on `sessions` is partial (`revoked_at IS NULL`); finding it
again on every refresh would scan the table.

NOT NULL with no default: nothing has created a session before T-3.3, so the
table is empty in every environment, and a row that somehow exists fails this
loudly rather than getting an invented sign-in time.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "684b79a19e8b"
down_revision: str | Sequence[str] | None = "89b155534dcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("auth_time", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "auth_time")
