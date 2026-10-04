"""price reopen and extend together

Revision ID: e0a0c47fa4ff
Revises: a1d7de534ef7
Create Date: 2026-10-04 23:10:13.732299

`action_prices` (D-098, T-5.2): re-opening an expired Thread costs 2 Velas, down
from D-004's 3, and Extend (D-097), new, costs 10. One migration, because D-098
ties them: Extend costs what five re-opens do, so it pays for itself after five
lapses. Change neither price without the other.

Upserts: afterwards each row holds the decided price, whatever it held before,
and a missing row is written rather than skipped. The downgrade puts D-004's 3
back and removes Extend's row, which nothing references: a ledger row names a
reason, never a price row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0a0c47fa4ff"
down_revision: str | Sequence[str] | None = "a1d7de534ef7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICES = {"thread_reopen": 2, "thread_extend": 10}

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
    """Downgrade schema: D-004's re-open, and no Extend."""
    op.execute(
        sa.delete(action_prices).where(action_prices.c.action == "thread_extend")
    )
    op.execute(
        sa.update(action_prices)
        .where(action_prices.c.action == "thread_reopen")
        .values(credits=3)
    )
