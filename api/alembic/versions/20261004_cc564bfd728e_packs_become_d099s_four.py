"""packs become d099s four

Revision ID: cc564bfd728e
Revises: b270d197e38a
Create Date: 2026-10-04 23:10:14.657338

`credit_packs` (D-099, D-250, T-5.2): variant A becomes D-099's four packs,
₹1,500 → 30 · ₹4,500 → 100 · ₹6,000 → 250 · ₹10,000 → 450 Velas, each with the
20% first-purchase bonus (the column's default; D-231 keeps it). The ₹4,500 pack
is dominated on purpose: ₹1,500 more buys 150 more Velas (D-099). Don't "fix" it.

- `pack-100` keeps its id and its 100 Velas, and costs ₹4,500, up from ₹4,000:
  a price change is a row update, since `payments` copies amount and credits at
  order time (D-005).
- `pack-30`, `pack-250` and `pack-450` are new.
- `pack-25`, `pack-50` and `pack-75` are retired, `active = false`, never
  deleted: `payments` points at packs (rule 12), and their ids name their Velas.

Upserts for the four, so afterwards each holds D-099's values. The downgrade
puts D-005's ladder back, and refuses, by foreign key, once a payment names a
new pack. `entry-25`, variant B, is the next migration's.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cc564bfd728e"
down_revision: str | Sequence[str] | None = "b270d197e38a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# id, credits, price in paise (D-029), sort.
PACKS = (
    ("pack-30", 30, 150_000, 1),
    ("pack-100", 100, 450_000, 2),
    ("pack-250", 250, 600_000, 3),
    ("pack-450", 450, 1_000_000, 4),
)
RETIRED = ("pack-25", "pack-50", "pack-75")
NEW = ("pack-30", "pack-250", "pack-450")

credit_packs = sa.table(
    "credit_packs",
    sa.column("id"),
    sa.column("credits"),
    sa.column("price_paise"),
    sa.column("sort"),
    sa.column("variant"),
    sa.column("active"),
)


def upgrade() -> None:
    """Upgrade schema."""
    insert = postgresql.insert(credit_packs).values(
        [
            {
                "id": pack_id,
                "credits": credits,
                "price_paise": price_paise,
                "sort": sort,
                "variant": "A",
                "active": True,
            }
            for pack_id, credits, price_paise, sort in PACKS
        ]
    )
    op.execute(
        insert.on_conflict_do_update(
            index_elements=[credit_packs.c.id],
            set_={
                column: insert.excluded[column]
                for column in ("credits", "price_paise", "sort", "variant", "active")
            },
        )
    )
    op.execute(
        sa.update(credit_packs)
        .where(credit_packs.c.id.in_(RETIRED))
        .values(active=False)
    )


def downgrade() -> None:
    """Downgrade schema: D-005's ladder."""
    op.execute(sa.delete(credit_packs).where(credit_packs.c.id.in_(NEW)))
    op.execute(
        sa.update(credit_packs)
        .where(credit_packs.c.id == "pack-100")
        .values(price_paise=400_000, sort=4)
    )
    op.execute(
        sa.update(credit_packs)
        .where(credit_packs.c.id.in_(RETIRED))
        .values(active=True)
    )
