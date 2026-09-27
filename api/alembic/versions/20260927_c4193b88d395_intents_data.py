"""intents data

Revision ID: c4193b88d395
Revises: edf91547331e
Create Date: 2026-09-27 01:23:25.038322

The 10 intents (P-25, D-041): the founder's list, in the founder's order, in
sentence case like interests, since both show as chips on the same profile.

Same pattern as T-1.14's reference data: the insert is ON CONFLICT DO NOTHING, so
running it again changes nothing and never resets a label tuned since; the table
is written through an sa.table() stand-in, not the model (rule 11); downgrade()
deletes exactly the seeded ids, and the RESTRICT foreign key from
profile_intents refuses once an intent has been picked.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4193b88d395"
down_revision: str | Sequence[str] | None = "edf91547331e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# What you're looking for. Users pick 1 to 3 (T-3.6). Ids are fixed, 1 upward in
# this order: the API takes intent_ids.
INTENTS = (
    "Something serious",
    "Long term",
    "Situationship",
    "Casual dating",
    "Just one night",
    "No strings attached",
    "Open relationship",
    "Discreet",
    "Friendship",
    "Go with the flow",
)

intents = sa.table("intents", sa.column("id"), sa.column("slug"), sa.column("label"))


def _slug(label: str) -> str:
    return label.lower().replace(" ", "-")


def reference_data() -> list[postgresql.Insert]:
    """The insert, shared by upgrade() and the test that runs it twice."""
    rows: list[dict[str, object]] = [
        {"id": i, "slug": _slug(label), "label": label}
        for i, label in enumerate(INTENTS, start=1)
    ]
    return [postgresql.insert(intents).values(rows).on_conflict_do_nothing()]


def upgrade() -> None:
    """Upgrade schema."""
    for statement in reference_data():
        op.execute(statement)


def downgrade() -> None:
    """Downgrade schema: remove exactly the seeded ids."""
    op.execute(sa.delete(intents).where(intents.c.id.in_(range(1, len(INTENTS) + 1))))
