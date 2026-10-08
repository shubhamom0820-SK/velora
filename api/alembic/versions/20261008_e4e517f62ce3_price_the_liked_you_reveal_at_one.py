"""price the liked you reveal at one

Revision ID: e4e517f62ce3
Revises: 300945192d27
Create Date: 2026-10-08 12:07:05.503862

`action_prices` (P-370): revealing one "liked you" costs 1 Vela, the
founder's value from 8 October 2026 (D-004's note). A value change, not a
decision reopened: `liked_you_reveal` goes from D-004's 20, which T-1.14's
fa16c0908c2c wrote, to 1. No other row moves.

An upsert, as in 0cbb8f2bc7c8. The downgrade puts D-004's 20 back.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4e517f62ce3"
down_revision: str | Sequence[str] | None = "300945192d27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICES = {"liked_you_reveal": 1}

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
    """Downgrade schema: D-004's reveal."""
    op.execute(
        sa.update(action_prices)
        .where(action_prices.c.action == "liked_you_reveal")
        .values(credits=20)
    )
