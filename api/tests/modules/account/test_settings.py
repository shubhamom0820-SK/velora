"""`PATCH /me/settings` and pausing (T-9.6): the privacy switches, and hiding
the whole account for a while."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserStatus
from tests.conftest import MakeUser

SWITCHES = (
    "is_hidden",
    "hide_age",
    "hide_distance",
    "show_kudos",
    "show_gifts",
    "public_link",
)
DEFAULTS = {
    "is_hidden": False,
    "hide_age": False,
    "hide_distance": False,
    "show_kudos": True,
    "show_gifts": True,
    # Off for everyone until they turn it on (D-544).
    "public_link": False,
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


def _switches(response: Response) -> dict[str, bool]:
    profile = response.json()["profile"]
    return {name: profile[name] for name in SWITCHES}


async def _patch(client: AsyncClient, token: str, body: Any) -> Response:
    return await client.patch("/v1/me/settings", json=body, headers=_auth(token))


@pytest.mark.parametrize("switch", SWITCHES)
async def test_each_switch_sets_itself_and_nothing_else(
    client: AsyncClient, make_user: MakeUser, switch: str
) -> None:
    _, token = await make_user()
    flipped = not DEFAULTS[switch]

    response = await _patch(client, token, {switch: flipped})

    assert response.status_code == 200
    assert _switches(response) == {**DEFAULTS, switch: flipped}
    me = await client.get("/v1/me", headers=_auth(token))
    assert _switches(me) == {**DEFAULTS, switch: flipped}


async def test_several_at_once_and_back_again(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    hidden = await _patch(client, token, {"is_hidden": True, "hide_age": True})
    shown = await _patch(client, token, {"is_hidden": False})

    assert _switches(hidden) == {**DEFAULTS, "is_hidden": True, "hide_age": True}
    assert _switches(shown) == {**DEFAULTS, "hide_age": True}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"is_hidden": None},
        {"is_hiden": True},  # a typo must never look like it worked
        {"is_hidden": True, "show_photos": False},
        {"is_hidden": "yes"},
        {"is_hidden": 1},
        {"hide_age": "true"},
        [],
    ],
)
async def test_a_body_that_sets_nothing_known_is_refused(
    client: AsyncClient, make_user: MakeUser, body: Any
) -> None:
    _, token = await make_user()

    response = await _patch(client, token, body)

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    me = await client.get("/v1/me", headers=_auth(token))
    assert _switches(me) == DEFAULTS


ROUTES = [
    ("PATCH", "/v1/me/settings", {"is_hidden": True}),
    ("POST", "/v1/me/pause", None),
    ("DELETE", "/v1/me/pause", None),
    ("POST", "/v1/me/export", None),
    ("GET", "/v1/me/export", None),
    ("DELETE", "/v1/me", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_every_route_needs_a_sign_in(
    db: AsyncSession, client: AsyncClient, method: str, path: str, body: Any
) -> None:
    response = await client.request(method, path, json=body)

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_every_route_needs_onboarding_done(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    method: str,
    path: str,
    body: Any,
) -> None:
    user, token = await make_user(onboarded=False)

    response = await client.request(method, path, json=body, headers=_auth(token))

    assert response.status_code == 403
    assert _error(response) == {
        "code": "ONBOARDING_INCOMPLETE",
        "message": "Finish setting up your profile first.",
        "details": {"step": "seeking"},
    }
    await db.refresh(user)
    assert user.status is UserStatus.ACTIVE


# --- Pause -----------------------------------------------------------------------------


async def _status(client: AsyncClient, token: str) -> str:
    me = await client.get("/v1/me", headers=_auth(token))
    status: str = me.json()["status"]
    return status


async def test_pausing_and_resuming(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user()

    paused = await client.post("/v1/me/pause", headers=_auth(token))
    assert paused.status_code == 204
    assert paused.content == b""
    assert await _status(client, token) == "paused"

    resumed = await client.delete("/v1/me/pause", headers=_auth(token))
    assert resumed.status_code == 204
    assert await _status(client, token) == "active"


async def test_twice_is_once_either_way(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    for _ in range(2):
        assert (
            await client.post("/v1/me/pause", headers=_auth(token))
        ).status_code == 204
    assert await _status(client, token) == "paused"
    for _ in range(2):
        response = await client.delete("/v1/me/pause", headers=_auth(token))
        assert response.status_code == 204
    assert await _status(client, token) == "active"


async def test_pausing_leaves_the_switches_alone(
    client: AsyncClient, make_user: MakeUser
) -> None:
    """Pausing hides the account by its status; `is_hidden` stays the person's
    own choice, there when they come back."""
    _, token = await make_user()

    await client.post("/v1/me/pause", headers=_auth(token))
    await client.delete("/v1/me/pause", headers=_auth(token))

    me = await client.get("/v1/me", headers=_auth(token))
    assert _switches(me) == DEFAULTS
