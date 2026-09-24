"""The error envelope is a contract: every non-2xx looks the same (§3)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.errors import AppError
from app.main import create_app


class Body(BaseModel):
    """Module level on purpose.

    This file uses postponed annotations, so FastAPI resolves `body: Body` from
    module globals. A class defined inside the fixture would not be found, and
    the route would silently misbehave rather than fail loudly.
    """

    count: int


@pytest.fixture
async def failing_client() -> AsyncClient:
    """An app with routes that fail in each way we need to exercise."""
    app: FastAPI = create_app()

    @app.post("/v1/_test/validate")
    async def _validate(body: Body) -> dict[str, int]:
        return {"count": body.count}

    @app.get("/v1/_test/app-error")
    async def _app_error() -> None:
        raise AppError(
            "INSUFFICIENT_CREDITS",
            "You need 5 credits.",
            status=402,
            details={"required": 5, "balance": 2},
        )

    @app.get("/v1/_test/boom")
    async def _boom() -> None:
        raise ZeroDivisionError("internal detail that must not leak")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_unknown_route_returns_envelope(client: AsyncClient) -> None:
    """The task's 'Done when': an unknown route is NOT_FOUND in the envelope."""
    response = await client.get("/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "NOT_FOUND"
    assert isinstance(body["error"]["message"], str)


async def test_app_error_preserves_code_status_and_details(
    failing_client: AsyncClient,
) -> None:
    response = await failing_client.get("/v1/_test/app-error")

    assert response.status_code == 402
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_CREDITS"
    assert error["message"] == "You need 5 credits."
    assert error["details"] == {"required": 5, "balance": 2}


async def test_validation_error_is_400_validation_error(
    failing_client: AsyncClient,
) -> None:
    response = await failing_client.post(
        "/v1/_test/validate", json={"count": "not-a-number"}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"][0]["field"] == "count"


async def test_unhandled_exception_is_500_internal_and_leaks_nothing(
    failing_client: AsyncClient,
) -> None:
    response = await failing_client.get("/v1/_test/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL"
    assert "ZeroDivisionError" not in response.text
    assert "internal detail" not in response.text


async def test_method_not_allowed_uses_the_envelope(
    failing_client: AsyncClient,
) -> None:
    response = await failing_client.get("/v1/_test/validate")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_request_id_is_echoed_when_supplied(client: AsyncClient) -> None:
    response = await client.get(
        "/v1/does-not-exist", headers={"X-Request-ID": "abc-123"}
    )

    assert response.headers["X-Request-ID"] == "abc-123"


async def test_request_id_is_generated_when_absent(client: AsyncClient) -> None:
    response = await client.get("/v1/does-not-exist")

    assert response.headers.get("X-Request-ID")
