"""Response bodies for the health probes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CheckResult = Literal["ok", "fail"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessChecks(BaseModel):
    database: CheckResult
    redis: CheckResult


class ReadyResponse(BaseModel):
    status: Literal["ok"] = "ok"
    checks: ReadinessChecks
