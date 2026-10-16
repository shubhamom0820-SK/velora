"""Every `/v1/admin/*` route carries its own role check (T-9.5, P-30): the web's
gate is UX, and the API's `require_role` is the only thing guarding admin data
(D-024). Read from the app's own routes, so a route added later without one
fails here, whatever it does.

Refused before anything is read: no token is `AUTH_REQUIRED`; a user's token
is `FORBIDDEN`, and so is a moderator's on what only an admin may do (D-483,
D-582, D-922, D-923). None of them writes `audit_log`.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.main import create_app
from app.modules.admin.router import router as admin_router
from tests.conftest import MakeUser, make_test_settings
from tests.modules.admin.support import REASON, audits, auth, error, staff

pytestmark = pytest.mark.usefixtures("test_redis")

# An `Idempotency-Key` of the right shape, for the route that takes one.
KEY = f"key-{uuid.uuid4().hex[:12]}"

# What only an admin may call at all; the rest take a moderator too, and the
# panel refuses a moderator ban, unban and unfreeze itself (test_admin_status).
ADMIN_ONLY = {
    ("GET", "/v1/admin/turnover"),
    ("GET", "/v1/admin/refund-requests"),
    ("POST", "/v1/admin/refund-requests/{claim_id}/resolve"),
    ("POST", "/v1/admin/users/{user_id}/credits"),
}


def _admin_routes() -> list[tuple[str, str]]:
    """Every `/v1/admin` operation the app serves, from its OpenAPI schema,
    whichever router declares it."""
    paths = create_app(make_test_settings()).openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/v1/admin")
        for method in operations
    )


ROUTES = _admin_routes()


def _role_checks(method: str, path: str) -> list[str]:
    """The `require_role` dependencies the route itself declares."""
    for route in admin_router.routes:
        if (
            isinstance(route, APIRoute)
            and "/v1" + route.path == path
            and method in (route.methods or set())
        ):
            return [
                dependency.call.__qualname__
                for dependency in route.dependant.dependencies
                if dependency.call is not None
                and dependency.call.__qualname__.startswith("require_role.")
            ]
    raise AssertionError(f"no route {method} {path} on the admin router")


def _call(path: str) -> str:
    return path.format(
        **{
            name: uuid.uuid4()
            for name in ("claim_id", "user_id", "report_id", "photo_id", "thread_id")
        }
    )


async def _send(
    client: AsyncClient, method: str, path: str, headers: dict[str, str]
) -> Any:
    return await client.request(method, _call(path), headers=headers, json={})


def test_the_panel_has_every_route_04_api_names() -> None:
    assert ROUTES == sorted(
        [
            ("GET", "/v1/admin/audit"),
            ("GET", "/v1/admin/freezes"),
            ("GET", "/v1/admin/metrics"),
            ("GET", "/v1/admin/moderation"),
            ("GET", "/v1/admin/refund-requests"),
            ("GET", "/v1/admin/reports"),
            ("GET", "/v1/admin/threads/{thread_id}/messages"),
            ("GET", "/v1/admin/turnover"),
            ("GET", "/v1/admin/users"),
            ("GET", "/v1/admin/users/{user_id}"),
            ("POST", "/v1/admin/photos/{photo_id}/decide"),
            ("POST", "/v1/admin/refund-requests/{claim_id}/resolve"),
            ("POST", "/v1/admin/reports/{report_id}/resolve"),
            ("POST", "/v1/admin/users/{user_id}/credits"),
            ("POST", "/v1/admin/users/{user_id}/status"),
        ]
    )


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_admin_route_declares_its_own_role_check(method: str, path: str) -> None:
    assert len(_role_checks(method, path)) == 1, (method, path)


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_no_token_is_auth_required(
    db: AsyncSession, client: AsyncClient, method: str, path: str
) -> None:
    response = await _send(client, method, path, {})

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_a_user_is_forbidden_and_nothing_is_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, method: str, path: str
) -> None:
    user_id, token = await staff(make_user, Role.USER)

    response = await _send(client, method, path, auth(token, KEY))

    assert response.status_code == 403, response.text
    assert error(response)["code"] == "FORBIDDEN"
    assert await audits(db, user_id) == []


@pytest.mark.parametrize(("method", "path"), sorted(ADMIN_ONLY))
async def test_a_moderator_is_forbidden_what_only_an_admin_may_call(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, method: str, path: str
) -> None:
    moderator_id, token = await staff(make_user, Role.MODERATOR)
    body = {"delta": 5, "reason": REASON} if path.endswith("/credits") else {}

    response = await client.request(
        method, _call(path), headers=auth(token, KEY), json=body
    )

    assert response.status_code == 403, response.text
    assert error(response)["code"] == "FORBIDDEN"
    assert await audits(db, moderator_id) == []


@pytest.mark.parametrize(
    ("method", "path"),
    sorted(set(ROUTES) - ADMIN_ONLY - {("GET", "/v1/admin/users/{user_id}")}),
)
async def test_a_moderator_reaches_the_rest(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, method: str, path: str
) -> None:
    """Past the role check: whatever answers next, it isn't FORBIDDEN."""
    _, token = await staff(make_user, Role.MODERATOR)

    response = await _send(client, method, path, auth(token))

    assert response.status_code != 403, response.text
