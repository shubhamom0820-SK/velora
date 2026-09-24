"""Liveness and readiness probes.

Mounted at the root, not under `/v1`: probes are read by Fly and uptime checks,
not by clients, and are not part of the versioned API (`02-ARCHITECTURE.md` §3).

This router calls `check_database()` and `check_redis()` directly, with no
service or repository in between. That is the one documented exception to
CLAUDE.md rule 8 — there are no business rules and no tables here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter

from app.core.db import check_database
from app.core.errors import AppError
from app.core.redis import check_redis
from app.modules.health.schemas import (
    CheckResult,
    HealthResponse,
    ReadinessChecks,
    ReadyResponse,
)

log = structlog.get_logger(__name__)

# How long one dependency may take to answer before it counts as down. Without
# a bound, a hung Postgres makes /readyz hang instead of fail, and the platform
# health check times out with no signal. Infrastructure timing, not a product
# limit, so it does not belong in app_config.
READINESS_TIMEOUT_S = 2.0

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> HealthResponse:
    """Liveness: the process is up. Never touches a dependency.

    If this depended on Postgres or Redis, a blip in either would make the
    platform restart healthy API processes, turning a partial outage into a
    full one.
    """
    return HealthResponse()


async def _probe(name: str, check: Callable[[], Awaitable[None]]) -> CheckResult:
    try:
        await asyncio.wait_for(check(), timeout=READINESS_TIMEOUT_S)
    # Any failure means not ready: asyncpg, redis, OS and timeout errors all
    # differ. Exception, not BaseException, so cancellation still propagates.
    except Exception as exc:  # noqa: BLE001
        # Type only: a connection error's message can carry the DSN (rule 15).
        log.warning("readiness_check_failed", check=name, exc_type=type(exc).__name__)
        return "fail"
    return "ok"


@router.get(
    "/readyz",
    responses={
        503: {"description": "A dependency is not ready; error code NOT_READY."}
    },
)
async def readyz() -> ReadyResponse:
    """Readiness: Postgres and Redis both answer. 503 `NOT_READY` otherwise."""
    database, redis = await asyncio.gather(
        _probe("database", check_database),
        _probe("redis", check_redis),
    )
    checks = ReadinessChecks(database=database, redis=redis)

    if database == "fail" or redis == "fail":
        raise AppError(
            "NOT_READY",
            "The service is not ready.",
            status=503,
            details=checks.model_dump(),
        )
    return ReadyResponse(checks=checks)
