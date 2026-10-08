"""a private photo's scored copy

Revision ID: 8243172d0af6
Revises: d4f1d16b2191
Create Date: 2026-10-08 23:00:00.000000

P-79 and P-301 closed (D-700): `photos.scored_key`, where moderation writes an
approved private photo's re-encoded bytes, the ones Sightengine scored, under a
prefix no presigned PUT URL ever covers. The upload's URL lasts five minutes
and outlives `complete`, so the upload's own key can hold bytes nobody scored;
T-8.4's album is rendered only from this one.

A column rather than a key worked out from the photo's id, so the two lists
of files behind a person's rows (the erasure's and D-078's) are held to it by
their tests, which require every `*_key` column on those tables.

The downgrade refuses while any photo has one: dropping the column would leave
those files where neither deletion looks for them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8243172d0af6"
down_revision: str | Sequence[str] | None = "d4f1d16b2191"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("photos", sa.Column("scored_key", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema: refused while any photo has a scored copy."""
    held = op.get_bind().scalar(
        sa.text("select count(*) from photos where scored_key is not null")
    )
    if held:
        raise RuntimeError(
            f"{held} photos have a scored copy in storage, and without the column "
            "no deletion would find it (D-700)"
        )
    op.drop_column("photos", "scored_key")
