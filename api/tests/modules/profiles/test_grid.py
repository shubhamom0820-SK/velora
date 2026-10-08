"""D-490 (P-120): a stored position is a point of the 0.01° grid, never the
exact one. A move inside one cell stores the same point, the area is still found
from the exact position (D-220), the database refuses anything off the grid, and
the migration moved the rows already stored."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import OnboardingStep
from app.modules.profiles import rules
from app.modules.profiles.models import LOCATION_ON_GRID
from tests.conftest import MakeUser
from tests.modules.onboarding.test_guard import _alembic

pytestmark = pytest.mark.usefixtures("test_redis")

SNAPPED = "4c71a9e2b058"
ON_GRID = "9b4e0d2c7a15"
BEFORE = "e4e517f62ce3"

# Four positions inside the cell whose grid point is 31.22, 75.77 (Phagwara):
# each within half a cell of it, so each is stored there.
ONE_CELL = [
    (31.2151, 75.7651),
    (31.2249, 75.7749),
    (31.2199, 75.7702),
    (31.2160, 75.7740),
]


def _migration(filename: str) -> ModuleType:
    """A migration module by file name (the versions directory isn't a package)."""
    path = Path(__file__).parents[3] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK_MIGRATION = "20261008_9b4e0d2c7a15_profiles_location_on_grid.py"
DATA_MIGRATION = "20261008_4c71a9e2b058_snap_profile_positions.py"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _user_at_username(
    db: AsyncSession, make_user: MakeUser
) -> tuple[uuid.UUID, str]:
    user, token = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.USERNAME
    await db.flush()
    return user.id, token


async def _stored(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT area_id, ST_Y(location::geometry) AS lat, "
                "ST_X(location::geometry) AS lng FROM profiles WHERE user_id = :id"
            ),
            {"id": user_id},
        )
    ).one()
    return dict(row._mapping)


def test_the_grid_is_one_number_in_the_rules_the_model_and_the_migrations() -> None:
    assert rules.GRID_DEG == 0.01
    assert f"ST_SnapToGrid(location::geometry, {rules.GRID_DEG})" in LOCATION_ON_GRID
    check = _migration(CHECK_MIGRATION)
    data = _migration(DATA_MIGRATION)
    assert check.ON_GRID == LOCATION_ON_GRID
    assert data.GRID_DEG == rules.GRID_DEG


async def test_every_position_inside_one_cell_is_stored_as_the_same_point(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The point of the grid: a move inside a cell tells nobody anything."""
    user_id, token = await _user_at_username(db, make_user)
    stored = []
    for lat, lng in ONE_CELL:
        response = await client.put(
            "/v1/me/location", json={"lat": lat, "lng": lng}, headers=_bearer(token)
        )
        assert response.status_code == 200
        row = await _stored(db, user_id)
        stored.append((row["lat"], row["lng"]))

    assert stored == [pytest.approx((31.22, 75.77), abs=1e-9)] * len(ONE_CELL)
    assert len(set(stored)) == 1


async def _exact_and_grid_far(
    db: AsyncSession, area: str, *, exact_within: bool
) -> tuple[float, float]:
    """A position due around `area`'s centroid whose exact point and grid
    point fall on opposite sides of `AREA_WITHIN_M`: inside exactly and
    outside on the grid if `exact_within`, else the other way round."""
    edge = rules.AREA_WITHIN_M
    found = (
        await db.execute(
            text(
                "SELECT ST_Y(p::geometry), ST_X(p::geometry) FROM ("
                " SELECT ST_Project(a.centroid, m::float8, radians(b::float8)) AS p,"
                " a.centroid AS c FROM areas a, generate_series(CAST(:low AS int), CAST(:high AS int)) m,"
                " generate_series(0, 355, 5) b WHERE a.city = 'Phagwara' AND a.name = :area"
                ") AS t WHERE (ST_Distance(p, c) <= :edge) = :exact"
                " AND (ST_Distance(ST_SnapToGrid(p::geometry, CAST(:grid AS float8))::geography, c)"
                " <= :edge) <> :exact LIMIT 1"
            ),
            {
                "area": area,
                "low": edge - 400 if exact_within else edge + 1,
                "high": edge - 1 if exact_within else edge + 400,
                "edge": edge,
                "exact": exact_within,
                "grid": rules.GRID_DEG,
            },
        )
    ).first()
    assert found is not None, "no such position near " + area
    return float(found[0]), float(found[1])


@pytest.mark.parametrize("exact_within", [True, False])
async def test_the_area_is_found_from_the_exact_position_not_its_grid_point(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, exact_within: bool
) -> None:
    """Around Bhullarai, the northernmost in town, nothing else is near: a
    position within 2 km of its centroid whose grid point is beyond takes it,
    and one beyond whose grid point is within doesn't (D-220 unchanged)."""
    lat, lng = await _exact_and_grid_far(db, "Bhullarai", exact_within=exact_within)
    bhullarai = await db.scalar(
        text("SELECT id FROM areas WHERE city = 'Phagwara' AND name = 'Bhullarai'")
    )
    user_id, token = await _user_at_username(db, make_user)

    response = await client.put(
        "/v1/me/location", json={"lat": lat, "lng": lng}, headers=_bearer(token)
    )

    assert response.status_code == 200
    assert (await _stored(db, user_id))["area_id"] == (
        bhullarai if exact_within else None
    )


async def test_the_database_refuses_a_position_off_the_grid(
    db: AsyncSession, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    write = text(
        "UPDATE profiles SET location = "
        "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography WHERE user_id = :id"
    )

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await db.execute(write, {"lat": 31.2139, "lng": 75.768, "id": user.id})

    assert getattr(refused.value.orig, "sqlstate", None) == "23514"
    assert "ck_profiles_location_on_grid" in str(refused.value)
    # A grid point as the snap writes it is taken. A literal isn't always one:
    # 77.21 as a double isn't 7721 x 0.01, which is what the grid holds.
    snapped = text(
        "UPDATE profiles SET location = ST_SnapToGrid(ST_SetSRID("
        "ST_MakePoint(:lng, :lat), 4326), CAST(:grid AS float8))::geography "
        "WHERE user_id = :id"
    )
    for lat, lng in ((31.2139, 75.768), (6.5, 97.5), (28.6139, 77.209)):
        async with db.begin_nested():
            await db.execute(
                snapped, {"lat": lat, "lng": lng, "grid": rules.GRID_DEG, "id": user.id}
            )
    async with db.begin_nested():
        await db.execute(
            text("UPDATE profiles SET location = NULL WHERE user_id = :id"),
            {"id": user.id},
        )


async def test_the_migration_moves_the_positions_already_stored(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """Down to before the grid, an exact position written as T-4.10 wrote one,
    up again: it is on its grid point, its area untouched, and an empty one
    stays empty."""
    placed, _ = await make_user()
    empty, _ = await make_user()
    area_id = await db.scalar(
        text("SELECT id FROM areas WHERE city = 'Phagwara' AND name = 'Model Town'")
    )

    async with db.begin_nested():
        await _alembic(db, command.downgrade, BEFORE)
        await db.execute(
            text(
                "UPDATE profiles SET area_id = :area, location = "
                "ST_SetSRID(ST_MakePoint(75.768, 31.2139), 4326)::geography "
                "WHERE user_id = :id"
            ),
            {"area": area_id, "id": placed.id},
        )
        await _alembic(db, command.upgrade, SNAPPED)
        snapped = await _stored(db, placed.id)
        await _alembic(db, command.upgrade, ON_GRID)

    assert (snapped["lat"], snapped["lng"]) == pytest.approx((31.21, 75.77), abs=1e-9)
    assert snapped["area_id"] == area_id
    assert (await _stored(db, empty.id))["lat"] is None


async def test_the_downgrade_leaves_every_position_on_the_grid(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """It can't give back what nothing kept, and says so; the CHECK goes."""
    user, _ = await make_user()
    await db.execute(
        text(
            "UPDATE profiles SET location = "
            "ST_SnapToGrid(ST_SetSRID(ST_MakePoint(75.768, 31.2139), 4326), 0.01)"
            "::geography WHERE user_id = :id"
        ),
        {"id": user.id},
    )
    data = _migration(DATA_MIGRATION)
    assert "can't give the precision back" in (data.__doc__ or "")

    async with db.begin_nested():
        await _alembic(db, command.downgrade, BEFORE)
        after = await _stored(db, user.id)
        checks = set(
            await db.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = to_regclass('profiles') AND contype = 'c'"
                )
            )
        )
        await _alembic(db, command.upgrade, ON_GRID)

    assert (after["lat"], after["lng"]) == pytest.approx((31.21, 75.77), abs=1e-9)
    assert "ck_profiles_location_on_grid" not in checks
