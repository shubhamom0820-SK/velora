"""profiles location on grid

Revision ID: 9b4e0d2c7a15
Revises: 4c71a9e2b058
Create Date: 2026-10-08 12:01:00

`ck_profiles_location_on_grid` (D-490, P-120): `profiles.location` holds only
points of the 0.01° grid, so no writer, the seed or a later task's included,
can store an exact position by forgetting to snap it. A grid point snapped again
stays where it is, which is the test. NULL passes, as every CHECK does.

4c71a9e2b058, before this, moved the rows already stored.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b4e0d2c7a15"
down_revision: str | Sequence[str] | None = "4c71a9e2b058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# As the model writes it (app/modules/profiles/models.py, LOCATION_ON_GRID).
NAME = "ck_profiles_location_on_grid"
ON_GRID = "ST_Equals(location::geometry, ST_SnapToGrid(location::geometry, 0.01))"


def upgrade() -> None:
    op.create_check_constraint(op.f(NAME), "profiles", ON_GRID)


def downgrade() -> None:
    op.drop_constraint(op.f(NAME), "profiles", type_="check")
