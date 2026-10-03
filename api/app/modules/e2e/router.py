"""Test-only: the code the fake SMS provider last sent a number (T-3.13).

Playwright reads sign-in codes here (06-TESTING). `create_app()` mounts it only
where `ENV` is local and `SMS_PROVIDER` is fake, an allowlist (rule 16), and
it is never in OpenAPI, so `make types` is the same everywhere. 04-API lists
it under "Local only".
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.modules.e2e import service
from app.modules.e2e.schemas import LastCode, LastCodeQuery

router = APIRouter(prefix="/test", tags=["test"], include_in_schema=False)


@router.post("/sms/last-code")
async def sms_last_code(body: LastCodeQuery, request: Request) -> LastCode:
    return LastCode(code=service.last_code(request.app.state.providers.sms, body.phone))
