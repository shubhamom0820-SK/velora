"""gifts become d231s four

Revision ID: 8f09b5c19ccd
Revises: 1a2d25cb6d4a
Create Date: 2026-10-04 23:10:15.119135

`gifts` (D-231, D-252, T-5.2): four gifts at 5, 10, 15 and 20 Velas replace
D-016's six (0, 0, 2, 2, 4, 4). The four are the ones D-016 already charged
for, in rising order of what they say: a coffee, a rose, chocolates, a teddy.
`smile` and `wave`, the free two, are retired, `active = false`, never deleted:
`gift_sends` points at gifts (rule 12).

The four keep their ids and are repriced in place: `gift_sends.credits_charged`
copies the price when a gift is sent, so no history changes, and none existed
when this was written (T-8.9 builds sending). Upserts, so afterwards each row
holds D-231's values. The downgrade puts D-016's six back, all active.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f09b5c19ccd"
down_revision: str | Sequence[str] | None = "1a2d25cb6d4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# id, label, asset, credits, sort.
FOUR = (
    ("coffee", "Coffee", "☕", 5, 1),
    ("rose", "Rose", "🌹", 10, 2),
    ("chocolate", "Chocolate", "🍫", 15, 3),
    ("teddy", "Teddy", "🧸", 20, 4),
)
RETIRED = ("smile", "wave")
# D-016's six, as T-1.14 seeded them.
SIX = (
    ("smile", "Smile", "😊", 0, 1),
    ("wave", "Wave", "👋", 0, 2),
    ("rose", "Rose", "🌹", 2, 3),
    ("coffee", "Coffee", "☕", 2, 4),
    ("chocolate", "Chocolate", "🍫", 4, 5),
    ("teddy", "Teddy", "🧸", 4, 6),
)

gifts = sa.table(
    "gifts",
    sa.column("id"),
    sa.column("label"),
    sa.column("asset"),
    sa.column("credits"),
    sa.column("sort"),
    sa.column("active"),
)


def _upsert(rows: Sequence[tuple[str, str, str, int, int]]) -> None:
    insert = postgresql.insert(gifts).values(
        [
            {
                "id": gift_id,
                "label": label,
                "asset": asset,
                "credits": credits,
                "sort": sort,
                "active": True,
            }
            for gift_id, label, asset, credits, sort in rows
        ]
    )
    op.execute(
        insert.on_conflict_do_update(
            index_elements=[gifts.c.id],
            set_={
                column: insert.excluded[column]
                for column in ("label", "asset", "credits", "sort", "active")
            },
        )
    )


def upgrade() -> None:
    """Upgrade schema."""
    _upsert(FOUR)
    op.execute(sa.update(gifts).where(gifts.c.id.in_(RETIRED)).values(active=False))


def downgrade() -> None:
    """Downgrade schema: D-016's six."""
    _upsert(SIX)
