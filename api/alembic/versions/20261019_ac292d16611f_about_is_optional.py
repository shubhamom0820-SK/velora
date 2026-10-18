"""about is optional

Revision ID: ac292d16611f
Revises: 7c8a628fd3d7
Create Date: 2026-10-19 09:00:00.000000

**The bio is optional** (P-851, D-951; the founder, 14 October 2026: "bio mei
40 character likhna needed nahi hona chaiye they can skip"). None is NULL, as
before the about step; a bio is 1 to 300 characters. NULL passes the CHECK,
and `''` doesn't, so a profile says "no bio" one way only. Every row there is
NULL or 40 to 300 characters, so the new rule holds on any database as it
stands, with no reset.

The downgrade puts 3571ffd8d110's 40 to 300 back, refused while any bio is
shorter than 40: there is no truthful bio to put in its place.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ac292d16611f"
down_revision: str | Sequence[str] | None = "7c8a628fd3d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "about_length"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f(f"ck_profiles_{NAME}"), "profiles", type_="check")
    op.create_check_constraint(NAME, "profiles", "char_length(about) BETWEEN 1 AND 300")


def downgrade() -> None:
    """Downgrade schema: refused while a bio is shorter than 40 characters."""
    short = op.get_bind().scalar(
        sa.text("select count(*) from profiles where char_length(about) < 40")
    )
    if short:
        raise RuntimeError(
            f"{short} bios are shorter than 40 characters, and the rule before "
            "P-851 needs 40: there is no truthful bio to put in their place (D-951)"
        )
    op.drop_constraint(op.f(f"ck_profiles_{NAME}"), "profiles", type_="check")
    op.create_check_constraint(
        NAME, "profiles", "char_length(about) BETWEEN 40 AND 300"
    )
