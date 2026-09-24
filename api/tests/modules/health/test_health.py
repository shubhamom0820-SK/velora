"""Liveness and readiness probes.

Failure paths patch the check functions — Redis cannot be stopped from inside a
test. The happy path hits the real Postgres and Redis from `make infra-up`, and
skips (rather than fails) when they are not running, so CI without Docker stays
quiet (T-1.20).
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.redis import close_redis
from app.modules.health import router as health_router

_FAKE_DSN = "postgresql+asyncpg://velora:hunter2@db.internal.example:6543/velora"


def _reachable(url: str) -> bool:
    parts = urlsplit(url)
    if parts.hostname is None or parts.port is None:
        return False
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=0.5):
            return True
    except OSError:
        return False


_settings = get_settings()
requires_infra = pytest.mark.skipif(
    not (_reachable(_settings.DATABASE_URL) and _reachable(_settings.REDIS_URL)),
    reason="Postgres or Redis not reachable — start them with `make infra-up`",
)


@pytest.fixture(autouse=True)
async def _release_connections() -> AsyncIterator[None]:
    """Pools are bound to the event loop that opened them, and each test gets a
    fresh loop — so close them after every test rather than share them."""
    yield
    await close_redis()
    await dispose_engine()


def _patch_checks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    database_fails: bool = False,
    redis_fails: bool = False,
) -> list[str]:
    """Replace both checks; return the list each call is recorded into."""
    calls: list[str] = []

    async def fake_database() -> None:
        calls.append("database")
        if database_fails:
            raise ConnectionRefusedError(f"could not connect to {_FAKE_DSN}")

    async def fake_redis() -> None:
        calls.append("redis")
        if redis_fails:
            raise ConnectionError(
                "Error 61 connecting to 127.0.0.1:6379. Connection refused."
            )

    monkeypatch.setattr(health_router, "check_database", fake_database)
    monkeypatch.setattr(health_router, "check_redis", fake_redis)
    return calls


# --- /healthz -------------------------------------------------------------


async def test_healthz_is_200(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_does_not_touch_dependencies(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liveness must survive a dependency outage, or the platform restarts
    healthy processes and turns a partial outage into a full one."""
    calls = _patch_checks(monkeypatch, database_fails=True, redis_fails=True)

    response = await client.get("/healthz")

    assert response.status_code == 200
    assert calls == []


async def test_probes_are_not_under_v1(client: AsyncClient) -> None:
    assert (await client.get("/v1/healthz")).status_code == 404
    assert (await client.get("/v1/readyz")).status_code == 404


# --- /readyz --------------------------------------------------------------


@requires_infra
async def test_readyz_200_when_both_up(client: AsyncClient) -> None:
    """Against the real Postgres and Redis — no patching."""
    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok"},
    }


async def test_readyz_503_when_redis_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, redis_fails=True)

    response = await client.get("/readyz")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "NOT_READY"
    assert error["details"] == {"database": "ok", "redis": "fail"}


async def test_readyz_503_when_database_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database_fails=True)

    response = await client.get("/readyz")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "NOT_READY"
    assert error["details"] == {"database": "fail", "redis": "ok"}


async def test_readyz_503_when_both_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database_fails=True, redis_fails=True)

    response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["details"] == {"database": "fail", "redis": "fail"}


async def test_readyz_checks_both_even_when_one_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both are reported, so an incident shows everything that is down at once."""
    calls = _patch_checks(monkeypatch, database_fails=True)

    await client.get("/readyz")

    assert sorted(calls) == ["database", "redis"]


async def test_readyz_times_out_a_hung_dependency(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dependency that never answers counts as down instead of hanging /readyz."""
    _patch_checks(monkeypatch)

    async def hangs() -> None:
        await asyncio.sleep(3600)

    monkeypatch.setattr(health_router, "check_redis", hangs)
    monkeypatch.setattr(health_router, "READINESS_TIMEOUT_S", 0.05)

    response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["details"]["redis"] == "fail"


async def test_readyz_503_leaks_no_connection_details(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_checks(monkeypatch, database_fails=True, redis_fails=True)

    response = await client.get("/readyz")

    for secret in ("hunter2", "db.internal.example", "6543", "6379", "velora:"):
        assert secret not in response.text


async def test_readyz_logs_only_the_exception_type(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rule 15 / P-04: a connection error's message can carry the DSN."""
    logged: list[dict[str, Any]] = []

    class Recorder:
        def warning(self, event: str, **kwargs: Any) -> None:
            logged.append({"event": event, **kwargs})

    monkeypatch.setattr(health_router, "log", Recorder())
    _patch_checks(monkeypatch, database_fails=True)

    await client.get("/readyz")

    assert logged == [
        {
            "event": "readiness_check_failed",
            "check": "database",
            "exc_type": "ConnectionRefusedError",
        }
    ]
    assert "hunter2" not in repr(logged)
