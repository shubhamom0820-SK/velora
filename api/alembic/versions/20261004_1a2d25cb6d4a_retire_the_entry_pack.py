"""retire the entry pack

Revision ID: 1a2d25cb6d4a
Revises: cc564bfd728e
Create Date: 2026-10-04 23:10:14.887172

`credit_packs` (D-250, T-5.2): `entry-25`, variant B of T-10.4's price test,
is retired, not repriced. **The number is the argument:** ₹999 for 25 Velas is
₹40 a Vela, and D-099's entry pack is ₹50 a Vela, so keeping it would have left
the cheapest pack sitting below the ladder. T-10.4 can propose a fresh test
against D-099's packs when there are users to test on.

Retired is `active = false`, never a deletion: `payments` points at packs
(rule 12). Variant B now has no active pack, which T-8.1 handles (its plan says
how). The downgrade makes it active again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1a2d25cb6d4a"
down_revision: str | Sequence[str] | None = "cc564bfd728e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTRY = "entry-25"

credit_packs = sa.table("credit_packs", sa.column("id"), sa.column("active"))


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.update(credit_packs).where(credit_packs.c.id == ENTRY).values(active=False)
    )


def downgrade() -> None:
    """Downgrade schema: D-005's entry variant, active."""
    op.execute(
        sa.update(credit_packs).where(credit_packs.c.id == ENTRY).values(active=True)
    )
