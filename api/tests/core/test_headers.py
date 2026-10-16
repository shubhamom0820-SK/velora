"""The API's own security headers (P-42, T-3.3), read off real responses:
`nosniff` on every one, `no-store` on every `/v1` one, errors included."""

from __future__ import annotations

import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import FakeProviders
from tests.infra import API_DIR

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


ALLOWED_ORIGIN = "http://127.0.0.1:3000"  # the test settings' CORS_ORIGINS


def _cors(response: Response) -> dict[str, str]:
    return {
        name: value
        for name, value in response.headers.items()
        if name.startswith("access-control-")
    }


async def test_a_500_carries_the_cors_headers_a_200_does(
    app: FastAPI, client: AsyncClient
) -> None:
    """P-61: without them a browser can't read the INTERNAL envelope, and the
    web takes every 500 for a lost connection. Compared with what CORSMiddleware
    gives a 200, so the two can't drift."""

    @app.get("/v1/_test/ok")
    async def _ok() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/v1/_test/boom")
    async def _boom() -> None:
        raise RuntimeError("boom")

    origin = {"Origin": ALLOWED_ORIGIN}
    ok = await client.get("/v1/_test/ok", headers=origin)
    boom = await client.get("/v1/_test/boom", headers=origin)

    assert boom.status_code == 500
    assert boom.json()["error"]["code"] == "INTERNAL"
    assert _cors(boom) == {
        "access-control-allow-origin": ALLOWED_ORIGIN,
        "access-control-allow-credentials": "true",
        "access-control-expose-headers": "X-Request-ID",
    }
    assert _cors(boom) == _cors(ok)
    assert "Origin" in boom.headers["vary"]
    _assert_v1(boom)


@pytest.mark.parametrize(
    "headers",
    [{"Origin": "https://evil.example"}, {"Origin": ALLOWED_ORIGIN + "0"}, {}],
    ids=["another origin", "a near miss", "no origin"],
)
async def test_a_500_for_any_other_origin_carries_no_cors_header(
    app: FastAPI, client: AsyncClient, headers: dict[str, str]
) -> None:
    @app.get("/v1/_test/boom")
    async def _boom() -> None:
        raise RuntimeError("boom")

    response = await client.get("/v1/_test/boom", headers=headers)

    assert response.status_code == 500
    assert _cors(response) == {}
    _assert_v1(response)


async def test_a_cors_preflight_carries_both(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/waitlist",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    _assert_v1(response)


# --- The local web's origin (T-3.10) ------------------------------------------------


async def test_the_local_webs_credentialed_refresh_is_allowed(
    client: AsyncClient,
) -> None:
    """What the web's refresh needs from a browser: its own origin echoed, never
    `*`, with credentials, and `X-CSRF` allowed (D-055)."""
    response = await client.options(
        "/v1/auth/refresh",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed = {
        h.strip().lower()
        for h in response.headers["access-control-allow-headers"].split(",")
    }
    assert "x-csrf" in allowed


async def test_localhost_is_refused_so_the_cross_site_mistake_fails_loudly(
    client: AsyncClient,
) -> None:
    """`localhost:3000` calling `127.0.0.1:8000` is cross-site, so the `Lax`
    refresh cookie would silently not be sent. CORS refuses it instead, an
    error in the console rather than a session that never restores."""
    response = await client.options(
        "/v1/auth/refresh",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_the_example_env_names_exactly_the_local_web() -> None:
    """Parsed as a dotenv file, the way the API reads `.env`: exactly one origin."""
    values = dotenv_values(API_DIR / ".env.example")

    assert values["CORS_ORIGINS"] == "http://127.0.0.1:3000"
