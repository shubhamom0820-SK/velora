"""public photos require a position

Revision ID: 36af56c36916
Revises: 3571ffd8d110
Create Date: 2026-09-26 03:18:29.198471

Fixes ck_photos_public_position_range from T-1.9 (P-13). With position NULL,
`position BETWEEN 0 AND 5` is unknown, and Postgres passes a CHECK on unknown —
so slot-less public photos were allowed, though 03-SCHEMA.md ("0–5 for public;
0 = main") means every public photo holds a slot. T-1.9 is merged, so this is a
new migration rather than an edit (rule 11).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "36af56c36916"
down_revision: str | Sequence[str] | None = "3571ffd8d110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# op.f() marks the name final. Without it Alembic applies the naming convention
# again and looks for "ck_photos_ck_photos_public_position_range".
NAME = "ck_photos_public_position_range"
BEFORE = "kind <> 'public' OR position BETWEEN 0 AND 5"
AFTER = "kind <> 'public' OR (position IS NOT NULL AND position BETWEEN 0 AND 5)"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f(NAME), "photos", type_="check")
    op.create_check_constraint(op.f(NAME), "photos", AFTER)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f(NAME), "photos", type_="check")
    op.create_check_constraint(op.f(NAME), "photos", BEFORE)
