"""price private messages

Revision ID: 134555ebf46f
Revises: e0a0c47fa4ff
Create Date: 2026-10-04 23:10:13.963207

`action_prices` (D-231, T-5.2): a private message, sent from a profile with no
swipe and no match, costs 8 Velas for the first (`dm_open`, D-004's 5 until
now) and 2 for each after it (`dm_message`, new, D-251). One migration: they
are the two halves of one price.

Upserts, as in e0a0c47fa4ff. The downgrade puts D-004's 5 back and removes
`dm_message`'s row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "134555ebf46f"
down_revision: str | Sequence[str] | None = "e0a0c47fa4ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICES = {"dm_open": 8, "dm_message": 2}

action_prices = sa.table("action_prices", sa.column("action"), sa.column("credits"))


def upgrade() -> None:
    """Upgrade schema."""
    insert = postgresql.insert(action_prices).values(
        [{"action": action, "credits": credits} for action, credits in PRICES.items()]
    )
    op.execute(
        insert.on_conflict_do_update(
            index_elements=[action_prices.c.action],
            set_={"credits": insert.excluded.credits},
        )
    )


def downgrade() -> None:
    """Downgrade schema: D-004's direct message, and no later ones."""
    op.execute(sa.delete(action_prices).where(action_prices.c.action == "dm_message"))
    op.execute(
        sa.update(action_prices)
        .where(action_prices.c.action == "dm_open")
        .values(credits=5)
    )
