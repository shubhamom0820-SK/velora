"""a blurred copy of each public photo

Revision ID: 02f42ccb4d88
Revises: 8243172d0af6
Create Date: 2026-10-08 18:00:00.000000

`photos.blur_key` (T-6.7, D-543): the public-bucket key of the photo's blurred
copy, which a man sees in Liked you until he reveals who liked him. Its key is
a fresh random id, never the photo's: `p/{photo id}.jpg` is the photo itself,
so a key derived from the id would hand him the unblurred one. Null until the
worker has made it, and for every photo that isn't an approved public one.

**The downgrade refuses while any photo has one:** dropping the column would
lose the only record of where each blurred copy is, and a copy nobody can find
can never be deleted, at a photo's removal or an account's erasure (D-503).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02f42ccb4d88"
down_revision: str | Sequence[str] | None = "8243172d0af6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("photos", sa.Column("blur_key", sa.Text(), nullable=True))


def downgrade() -> None:
    held = op.get_bind().scalar(
        sa.text("select count(*) from photos where blur_key is not null")
    )
    if held:
        raise RuntimeError(
            f"{held} photos have a blurred copy in the public bucket: delete "
            "those files first, or they can never be found again (D-543)"
        )
    op.drop_column("photos", "blur_key")
