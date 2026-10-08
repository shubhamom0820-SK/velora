"""`GET /v1/areas` and `PUT /v1/me/location` (T-4.10, D-220): a position inside
India's box with the nearest area within 2 km, or a picked area at its
centroid; from the `username` step on, never moving it; and `Me` saying
whether the location is current, by the server's clock. Either is stored as its
point of D-490's grid, which `test_grid.py` holds."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep
from app.modules.profiles import rules
from app.modules.profiles.models import Area
from app.modules.profiles.router import LOCATION_SETS_PER_HOUR
from app.modules.users.models import User
from tests.conftest import CapturedLogs, MakeUser

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 5, 6, 30, tzinfo=UTC)

# Beside Model Town's centroid (31.2139, 75.7696), about 150 m west of it and
# 650 m from Guru Hargobind Nagar's, the nearest other.
NEAR_MODEL_TOWN = {"lat": 31.2139, "lng": 75.7680}
DELHI = {"lat": 28.6139, "lng": 77.2090}
# Where each is stored: its point of the 0.01° grid (D-490).
NEAR_MODEL_TOWN_ON_GRID = (31.21, 75.77)
DELHI_ON_GRID = (28.61, 77.21)

STEPS = list(OnboardingStep)
BEFORE = STEPS[: STEPS.index(OnboardingStep.USERNAME)]
FROM = STEPS[STEPS.index(OnboardingStep.USERNAME) :]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


def _fields(response: Response) -> set[str]:
    return {f["field"] for f in _error(response)["details"]["fields"]}


async def _put(client: AsyncClient, token: str, body: Any) -> Response:
    return await client.put("/v1/me/location", json=body, headers=_bearer(token))


async def _at(
    db: AsyncSession, make_user: MakeUser, step: OnboardingStep
) -> tuple[User, str, uuid.UUID]:
    """A user at `step`, their token, and their id, read now: a refused request
    rolls back and expires the loaded user."""
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    user.onboarding_step = step
    await db.flush()
    return user, token, user.id


async def _area_id(db: AsyncSession, name: str) -> uuid.UUID:
    found = await db.scalar(
        select(Area.id).where(Area.city == "Phagwara", Area.name == name)
    )
    assert found is not None, name
    return found


async def _stored(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """What the profile holds now, read past the session's cache."""
    row = (
        await db.execute(
            text(
                "SELECT area_id, location_updated_at, ST_Y(location::geometry) AS lat, "
                "ST_X(location::geometry) AS lng FROM profiles WHERE user_id = :id"
            ),
            {"id": user_id},
        )
    ).one()
    return dict(row._mapping)


async def _metres_from_centroid(
    db: AsyncSession, user_id: uuid.UUID, area_id: uuid.UUID
) -> float:
    metres = await db.scalar(
        text(
            "SELECT ST_Distance(p.location, a.centroid) FROM profiles p, areas a "
            "WHERE p.user_id = :user AND a.id = :area"
        ),
        {"user": user_id, "area": area_id},
    )
    assert metres is not None
    return float(metres)


# --- The areas ---------------------------------------------------------------------


async def test_areas_are_phagwaras_17_by_name_with_exactly_their_fields(
    db: AsyncSession, client: AsyncClient
) -> None:
    """Public: no token needed. Never a centroid: the picker shows names."""
    response = await client.get("/v1/areas")

    assert response.status_code == 200
    areas = response.json()
    assert len(areas) == 17
    assert {frozenset(a) for a in areas} == {frozenset({"id", "city", "name"})}
    assert {a["city"] for a in areas} == {"Phagwara"}
    names = [a["name"] for a in areas]
    # In any case, whatever the database's collation: "Law Gate", then "LPU".
    assert names == sorted(names, key=str.lower)
    assert "Model Town" in names and "Koramangala" not in names


async def test_a_city_matches_in_any_case_and_an_unseeded_one_has_none(
    db: AsyncSession, client: AsyncClient
) -> None:
    every = (await client.get("/v1/areas")).json()

    for city in ("Phagwara", "phagwara", "PHAGWARA"):
        response = await client.get("/v1/areas", params={"city": city})
        assert response.status_code == 200
        assert response.json() == every, city
    bengaluru = await client.get("/v1/areas", params={"city": "Bengaluru"})
    assert (bengaluru.status_code, bengaluru.json()) == (200, [])


async def test_a_city_longer_than_any_is_a_validation_error(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.get("/v1/areas", params={"city": "x" * 41})

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"


# --- A shared position --------------------------------------------------------------


async def test_a_position_is_stored_with_its_nearest_area_and_answers_me(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, NEAR_MODEL_TOWN)

    assert response.status_code == 200
    me = response.json()
    assert me["id"] == str(user_id)
    assert me["profile"]["location"] == "fresh"
    assert me["onboarding_step"] == "username"  # never moved (D-220)
    stored = await _stored(db, user_id)
    assert stored["area_id"] == await _area_id(db, "Model Town")
    assert stored["location_updated_at"] == START
    assert (stored["lat"], stored["lng"]) == pytest.approx(
        NEAR_MODEL_TOWN_ON_GRID, abs=1e-9
    )


async def test_a_position_far_from_every_area_has_none_replacing_a_picked_one(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)
    picked = await _area_id(db, "Hadiabad")
    assert (await _put(client, token, {"area_id": str(picked)})).status_code == 200

    response = await _put(client, token, DELHI)

    assert response.status_code == 200
    stored = await _stored(db, user_id)
    assert stored["area_id"] is None
    assert (stored["lat"], stored["lng"]) == pytest.approx(DELHI_ON_GRID, abs=1e-9)


@pytest.mark.parametrize(("metres", "within"), [(1990, True), (2010, False)])
async def test_an_area_is_taken_within_2_km_of_its_centroid_and_not_beyond(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    metres: int,
    within: bool,
) -> None:
    """Due north of Bhullarai, the northernmost in town: nothing else is near."""
    assert rules.AREA_WITHIN_M == 2000
    bhullarai = await _area_id(db, "Bhullarai")
    lat, lng = (
        await db.execute(
            text(
                "SELECT ST_Y(p::geometry), ST_X(p::geometry) FROM ("
                "SELECT ST_Project(centroid, CAST(:metres AS float8), 0.0) AS p FROM areas "
                "WHERE id = :id) AS projected"
            ),
            {"metres": metres, "id": bhullarai},
        )
    ).one()
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, {"lat": lat, "lng": lng})

    assert response.status_code == 200
    assert (await _stored(db, user_id))["area_id"] == (bhullarai if within else None)


@pytest.mark.parametrize(
    ("lat", "lng"),
    [(6.5, 68.0), (37.5, 97.5), (6.5, 97.5), (37.5, 68.0)],
)
async def test_the_corners_of_indias_box_are_inside(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, lat: float, lng: float
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, {"lat": lat, "lng": lng})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("lat", "lng", "refused"),
    [
        (6.49, 75.0, {"lat"}),
        (37.51, 75.0, {"lat"}),
        (20.0, 67.99, {"lng"}),
        (20.0, 97.51, {"lng"}),
        (51.5072, -0.1276, {"lat", "lng"}),  # London
        (0.0, 0.0, {"lat", "lng"}),  # where a broken reading lands
    ],
)
async def test_a_position_outside_indias_box_is_refused_and_nothing_stored(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    lat: float,
    lng: float,
    refused: set[str],
) -> None:
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, {"lat": lat, "lng": lng})

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    assert _fields(response) == refused
    problems = {f["problem"] for f in _error(response)["details"]["fields"]}
    assert all(p.startswith("must be inside India") for p in problems)
    stored = await _stored(db, user_id)
    assert (stored["lat"], stored["area_id"], stored["location_updated_at"]) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"lat": 31.2},
        {"lng": 75.7},
        {"lat": 31.2, "lng": None},
        {"lat": "31.2", "lng": "75.7"},  # numbers, never strings
        {"lat": True, "lng": 75.7},
        {"lat": 91, "lng": 75.7},
        {"lat": 31.2, "lng": 181},
        {"lat": 31.2, "lng": 75.7, "accuracy": 20},
        {"area_id": "model-town"},
        {"area_id": None},
        {"lat": 31.2, "lng": 75.7, "area_id": str(uuid.uuid4())},  # one or the other
        [31.2, 75.7],
    ],
)
async def test_bodies_the_schema_refuses_are_validation_errors(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: Any
) -> None:
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, body)

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    assert (await _stored(db, user_id))["location_updated_at"] is None


@pytest.mark.parametrize(
    ("body", "fields"),
    [
        ({"lat": 31.2}, {"position.lng"}),
        (
            {"lat": 31.2, "lng": 75.7, "area_id": str(uuid.uuid4())},
            {"area.lat", "area.lng"},
        ),
        ({"area_id": "model-town"}, {"area.area_id"}),
    ],
)
async def test_a_refused_body_names_only_the_fields_of_the_form_it_tried(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    body: dict[str, Any],
    fields: set[str],
) -> None:
    """A body naming an area is an area, any other a position: never both
    forms' failures at once."""
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, body)

    assert response.status_code == 400
    assert _fields(response) == fields


@pytest.mark.parametrize(
    "raw", ['{"lat": NaN, "lng": 75.7}', '{"lat": 31.2, "lng": Infinity}']
)
async def test_not_a_number_and_infinity_are_validation_errors(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, raw: str
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await client.put(
        "/v1/me/location",
        content=raw,
        headers={**_bearer(token), "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"


# --- A picked area -------------------------------------------------------------------


async def test_a_picked_area_is_stored_at_its_centroids_grid_point(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Law Gate's centroid is 31.2536, 75.6969: its grid point is 31.25, 75.70,
    about 500 m away (D-490)."""
    clock.freeze(START)
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)
    law_gate = await _area_id(db, "Law Gate")

    response = await _put(client, token, {"area_id": str(law_gate)})

    assert response.status_code == 200
    assert response.json()["profile"]["location"] == "fresh"
    stored = await _stored(db, user_id)
    assert (stored["area_id"], stored["location_updated_at"]) == (law_gate, START)
    assert (stored["lat"], stored["lng"]) == pytest.approx((31.25, 75.70), abs=1e-9)
    assert 0 < await _metres_from_centroid(db, user_id, law_gate) < 800


async def test_an_area_that_doesnt_exist_is_refused_and_nothing_stored(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, {"area_id": str(uuid.uuid4())})

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    assert _fields(response) == {"area_id"}
    assert (await _stored(db, user_id))["location_updated_at"] is None


# --- When it works -------------------------------------------------------------------


@pytest.mark.parametrize("step", BEFORE)
async def test_before_the_username_step_it_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    """The question comes after Name (D-220), so not before Name is done."""
    _, token, user_id = await _at(db, make_user, step)

    response = await _put(client, token, NEAR_MODEL_TOWN)

    assert response.status_code == 403
    error = _error(response)
    assert error["code"] == "ONBOARDING_INCOMPLETE"
    assert error["details"] == {"step": step.value}
    assert (await _stored(db, user_id))["location_updated_at"] is None


@pytest.mark.parametrize("step", FROM)
async def test_from_the_username_step_on_it_works_and_never_moves_the_step(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    _, token, user_id = await _at(db, make_user, step)

    response = await _put(client, token, NEAR_MODEL_TOWN)

    assert response.status_code == 200
    assert response.json()["onboarding_step"] == step.value
    step_now = await db.scalar(
        select(User.onboarding_step)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )
    assert step_now is step


async def test_without_a_token_it_is_auth_required(
    db: AsyncSession, client: AsyncClient
) -> None:
    response = await client.put("/v1/me/location", json=NEAR_MODEL_TOWN)

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"


async def test_past_ten_an_hour_it_is_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Refused tries count too: the limit is on asking, not on succeeding."""
    assert LOCATION_SETS_PER_HOUR == 10
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)
    for n in range(LOCATION_SETS_PER_HOUR):
        body = DELHI if n % 2 else {"lat": 0, "lng": 0}
        assert (await _put(client, token, body)).status_code in (200, 400)

    response = await _put(client, token, NEAR_MODEL_TOWN)

    assert response.status_code == 429
    error = _error(response)
    assert error["code"] == "RATE_LIMITED"
    assert 0 < error["details"]["retry_after_s"] <= 3600
    _, other, _ = await _at(db, make_user, OnboardingStep.USERNAME)
    assert (await _put(client, other, NEAR_MODEL_TOWN)).status_code == 200


# --- Me ------------------------------------------------------------------------------


async def test_me_says_none_then_fresh_then_stale_past_six_hours_by_the_server(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Aged by moving the stored time back: moving the clock six hours would
    expire the access token first."""
    clock.freeze(START)
    _, token, user_id = await _at(db, make_user, OnboardingStep.USERNAME)

    async def location() -> str:
        response = await client.get("/v1/me", headers=_bearer(token))
        state: str = response.json()["profile"]["location"]
        return state

    async def set_at(at: datetime) -> None:
        await db.execute(
            text("UPDATE profiles SET location_updated_at = :at WHERE user_id = :id"),
            {"at": at, "id": user_id},
        )

    assert await location() == "none"
    await _put(client, token, NEAR_MODEL_TOWN)
    assert await location() == "fresh"
    await set_at(START - timedelta(hours=6))
    assert await location() == "fresh"
    await set_at(START - timedelta(hours=6, microseconds=1))
    assert await location() == "stale"
    await _put(client, token, DELHI)
    assert await location() == "fresh"


# --- Rule 15 -------------------------------------------------------------------------


async def test_a_position_is_never_logged(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    refused = await _put(client, token, {"lat": 51.50721234, "lng": -0.12761234})
    stored = await _put(client, token, {"lat": 31.21395678, "lng": 75.76805678})

    assert (refused.status_code, stored.status_code) == (400, 200)
    for digits in ("51.507", "0.1276", "31.2139", "75.768"):
        assert digits not in captured_logs.text, digits
    captured_logs.assert_listening()


async def test_the_profile_row_is_the_one_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Another user's row is untouched by mine."""
    _, mine, my_id = await _at(db, make_user, OnboardingStep.USERNAME)
    _, _, their_id = await _at(db, make_user, OnboardingStep.USERNAME)

    assert (await _put(client, mine, NEAR_MODEL_TOWN)).status_code == 200

    assert (await _stored(db, my_id))["location_updated_at"] is not None
    assert (await _stored(db, their_id))["location_updated_at"] is None
