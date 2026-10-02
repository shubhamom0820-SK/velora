"""`POST /v1/waitlist` (T-2.3): one row per email, the same answer for a repeat
(D-057), and five tries a minute per client IP that a forged header can't
escape (D-056)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import build_redis

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


async def _post(client: AsyncClient, body: Any, **headers: str) -> Response:
    return await client.post("/v1/waitlist", json=body, headers=headers)


async def _rows(db: AsyncSession) -> list[tuple[str, str | None]]:
    result = await db.execute(
        text("select email::text, city from waitlist order by email")
    )
    return [(row.email, row.city) for row in result]


@pytest.fixture
async def fly_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A client for the app configured like Fly: the client's IP comes from
    `Fly-Client-IP`, the header Fly's proxy sets (D-056). Settings are read per
    request, so swapping them here is enough."""
    app.state.settings = app.state.settings.model_copy(
        update={"CLIENT_IP_HEADER": "Fly-Client-IP"}
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Joining --------------------------------------------------------------------


async def test_a_new_email_joins(client: AsyncClient, db: AsyncSession) -> None:
    response = await _post(client, {"email": " priya@example.com ", "city": " Pune "})

    assert response.status_code == 201
    assert response.json() == {}
    assert await _rows(db) == [("priya@example.com", "Pune")]


async def test_city_is_optional_and_blank_means_none(
    client: AsyncClient, db: AsyncSession
) -> None:
    assert (await _post(client, {"email": "a@example.com"})).status_code == 201
    assert (
        await _post(client, {"email": "b@example.com", "city": "  "})
    ).status_code == 201
    assert (
        await _post(client, {"email": "c@example.com", "city": None})
    ).status_code == 201

    assert await _rows(db) == [
        ("a@example.com", None),
        ("b@example.com", None),
        ("c@example.com", None),
    ]


async def test_a_repeat_answers_exactly_as_a_new_email_and_changes_nothing(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Anything else would make this an email checker (D-057)."""
    first = await _post(client, {"email": "Priya@Example.com", "city": "Pune"})
    repeat = await _post(client, {"email": "priya@example.COM", "city": "Delhi"})

    assert (repeat.status_code, repeat.content) == (first.status_code, first.content)
    assert repeat.headers["content-type"] == first.headers["content-type"]
    # One row, as first written: a repeat doesn't even move the city.
    assert await _rows(db) == [("Priya@Example.com", "Pune")]


async def test_the_email_is_never_logged(
    client: AsyncClient, db: AsyncSession, capfd: pytest.CaptureFixture[str]
) -> None:
    await _post(client, {"email": "never-logged@example.com"})
    await _post(client, {"email": "never-logged@example.com"})
    await _post(client, {"email": "never-logged-bad@"})

    out, err = capfd.readouterr()
    assert "never-logged" not in out + err


# --- Validation -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({}, "email"),
        ({"email": ""}, "email"),
        ({"email": "   "}, "email"),
        ({"email": "priya"}, "email"),
        ({"email": "priya@example"}, "email"),
        ({"email": "priya @example.com"}, "email"),
        ({"email": "priya@@example.com"}, "email"),
        ({"email": "a" * 243 + "@example.com"}, "email"),  # 255 characters
        ({"email": "priya@example.com", "city": "x" * 41}, "city"),
        ({"email": 42}, "email"),
    ],
)
async def test_an_invalid_body_is_refused_and_nothing_is_written(
    client: AsyncClient, db: AsyncSession, body: dict[str, Any], field: str
) -> None:
    response = await _post(client, body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [f["field"] for f in error["details"]["fields"]] == [field]
    assert await _rows(db) == []


async def test_the_longest_deliverable_email_is_accepted(
    client: AsyncClient, db: AsyncSession
) -> None:
    email = "a" * 242 + "@example.com"  # 254 characters

    assert (await _post(client, {"email": email})).status_code == 201


# --- The rate limit: 5 a minute per client IP ------------------------------------


async def _six_tries(client: AsyncClient, **headers: str) -> list[int]:
    return [
        (await _post(client, {"email": f"try{i}@example.com"}, **headers)).status_code
        for i in range(6)
    ]


async def test_the_sixth_try_in_a_minute_is_refused(
    client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(START)

    assert await _six_tries(client) == [201] * 5 + [429]
    refused = await _post(client, {"email": "late@example.com"})
    error = refused.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert error["message"] == "Too many tries. Wait a moment and try again."
    assert error["details"] == {"retry_after_s": 60}
    # Only the five that were let through were written.
    assert len(await _rows(db)) == 5


async def test_invalid_tries_count_toward_the_limit(
    client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(START)
    for _ in range(5):
        assert (await _post(client, {"email": "nope"})).status_code == 400

    assert (await _post(client, {"email": "fine@example.com"})).status_code == 429
    assert await _rows(db) == []


async def test_it_opens_again_as_the_window_slides(
    client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _six_tries(client)

    clock.advance(timedelta(seconds=59))
    assert (await _post(client, {"email": "early@example.com"})).status_code == 429
    clock.advance(timedelta(seconds=1))
    assert (await _post(client, {"email": "ontime@example.com"})).status_code == 201


async def test_on_fly_each_client_ip_has_its_own_allowance(
    fly_client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(START)

    assert await _six_tries(fly_client, **{"Fly-Client-IP": "203.0.113.7"}) == (
        [201] * 5 + [429]
    )
    other = await _post(
        fly_client, {"email": "other@example.com"}, **{"Fly-Client-IP": "203.0.113.8"}
    )
    assert other.status_code == 201


async def test_on_fly_a_forged_forwarded_for_escapes_nothing(
    fly_client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    """The limit holds however X-Forwarded-For is rewritten from try to try."""
    clock.freeze(START)
    statuses = [
        (
            await _post(
                fly_client,
                {"email": f"forged{i}@example.com"},
                **{
                    "Fly-Client-IP": "203.0.113.7",
                    "X-Forwarded-For": f"198.51.100.{i}",
                },
            )
        ).status_code
        for i in range(6)
    ]

    assert statuses == [201] * 5 + [429]


async def test_on_fly_one_ipv6_slash_64_is_one_client(
    fly_client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(START)
    statuses = [
        (
            await _post(
                fly_client,
                {"email": f"v6-{i}@example.com"},
                **{"Fly-Client-IP": f"2001:db8:1:2::{i + 1:x}"},
            )
        ).status_code
        for i in range(6)
    ]

    assert statuses == [201] * 5 + [429]
    next_door = await _post(
        fly_client,
        {"email": "next-door@example.com"},
        **{"Fly-Client-IP": "2001:db8:1:3::1"},
    )
    assert next_door.status_code == 201


async def test_on_fly_requests_without_the_header_share_one_allowance(
    fly_client: AsyncClient, db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(START)
    statuses = [
        (
            await _post(
                fly_client,
                {"email": f"noheader{i}@example.com"},
                **{"X-Forwarded-For": f"198.51.100.{i}"},
            )
        ).status_code
        for i in range(6)
    ]

    assert statuses == [201] * 5 + [429]


# --- Redis down: refused, not unlimited -------------------------------------------


async def test_without_redis_the_request_fails_and_nothing_is_written(
    app: FastAPI,
    client: AsyncClient,
    db: AsyncSession,
    capfd: pytest.CaptureFixture[str],
) -> None:
    await app.state.redis.aclose()
    # Port 1: nothing listens there, so every Redis command fails at once.
    app.state.redis = build_redis("redis://127.0.0.1:1/0")

    response = await _post(client, {"email": "no-redis@example.com"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert await _rows(db) == []
    out, err = capfd.readouterr()
    assert "no-redis@example.com" not in out + err
