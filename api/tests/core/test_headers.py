"""The API's own security headers (P-42, T-3.3), read off real responses:
`nosniff` on every one, `no-store` on every `/v1` one, errors included."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import FakeProviders

pytestmark = pytest.mark.usefixtures("test_redis")


def _assert_v1(response: Response) -> None:
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers.get_list("cache-control") == ["no-store"]


def _assert_outside_v1(response: Response) -> None:
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "cache-control" not in response.headers


async def test_a_public_v1_response(db: AsyncSession, client: AsyncClient) -> None:
    response = await client.post("/v1/waitlist", json={"email": "a@example.com"})

    assert response.status_code == 201
    _assert_v1(response)


async def test_a_sign_in_carrying_an_access_token(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    await client.post("/v1/auth/otp/send", json={"phone": "98123 45678"})
    code = fake_providers.sms.sent[-1].code

    response = await client.post(
        "/v1/auth/otp/verify", json={"phone": "98123 45678", "otp": code}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    _assert_v1(response)


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("POST", "/v1/waitlist", {"email": "not-an-email"}, 400),
        ("GET", "/v1/no-such-route", None, 404),
        ("GET", "/v1", None, 404),
        ("POST", "/v1/auth/otp/verify", {"phone": "98123 45678", "otp": "123456"}, 400),
    ],
)
async def test_v1_errors_carry_both(
    db: AsyncSession,
    client: AsyncClient,
    method: str,
    path: str,
    body: object,
    status: int,
) -> None:
    response = await client.request(method, path, json=body)

    assert response.status_code == status
    _assert_v1(response)


async def test_the_probes_and_paths_outside_v1_get_nosniff_only(
    client: AsyncClient,
) -> None:
    _assert_outside_v1(await client.get("/healthz"))
    _assert_outside_v1(await client.get("/no-such-route"))
    # A path that only starts like the prefix isn't under it.
    _assert_outside_v1(await client.get("/v1x"))


async def test_a_500_carries_both(app: FastAPI, client: AsyncClient) -> None:
    """Starlette builds a 500 outside every middleware; errors.py adds them."""

    @app.get("/v1/_test/boom")
    async def _boom() -> None:
        raise RuntimeError("boom")

    response = await client.get("/v1/_test/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    _assert_v1(response)


async def test_a_cors_preflight_carries_both(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/waitlist",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    _assert_v1(response)
