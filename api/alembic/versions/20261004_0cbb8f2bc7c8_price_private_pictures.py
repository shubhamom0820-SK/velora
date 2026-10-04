"""price private pictures

Revision ID: 0cbb8f2bc7c8
Revises: 134555ebf46f
Create Date: 2026-10-04 23:10:14.192156

`action_prices` (D-231, T-5.2): viewing private pictures costs 1 Vela. It is
the album request (T-8.4) under another name, so `album_request` goes from
D-004's 5 to 1, and nothing comes back when a request is declined (D-230).

An upsert, as in e0a0c47fa4ff. The downgrade puts D-004's 5 back.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0cbb8f2bc7c8"
down_revision: str | Sequence[str] | None = "134555ebf46f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICES = {"album_request": 1}

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
    """Downgrade schema: D-004's album request."""
    op.execute(
        sa.update(action_prices)
        .where(action_prices.c.action == "album_request")
        .values(credits=5)
    )
