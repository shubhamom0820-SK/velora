"""snap profile positions

Revision ID: 4c71a9e2b058
Revises: e4e517f62ce3
Create Date: 2026-10-08 12:00:00

Every stored position moves to the nearest point of a 0.01° grid (D-490, P-120).
Until now `profiles.location` held the exact point a browser shared, and
discovery would have measured between exact points: read a woman's distance, or
just whether she is inside the 25 km radius, from a few places of your own
choosing (`PUT /me/location` takes any point in India), and the circles cross
where she lives. On grid points, a move inside one cell (about 1.1 by 1.0 km
here) changes nothing, and the most anyone can learn is which cell she is in.

Each row's area stays as it was: it was found from the exact point (D-220), and
the API still finds it that way before storing the grid point.

**The downgrade can't give the precision back.** The exact points are gone once
this runs; nothing kept them, on purpose. So the downgrade changes no row and
says so: going back to base leaves every position on the grid, which the code
before this migration reads like any other point. 9b4e0d2c7a15, next, adds the
CHECK that keeps every later write on the grid.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c71a9e2b058"
down_revision: str | Sequence[str] | None = "e4e517f62ce3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# rules.GRID_DEG as it was written here; a migration never imports app code.
GRID_DEG = 0.01


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE profiles "
            "SET location = ST_SnapToGrid(location::geometry, :grid)::geography "
            "WHERE location IS NOT NULL "
            "AND NOT ST_Equals(location::geometry, "
            "ST_SnapToGrid(location::geometry, :grid))"
        ),
        {"grid": GRID_DEG},
    )


def downgrade() -> None:
    # Nothing to undo that can be undone: the exact points no longer exist.
    pass
