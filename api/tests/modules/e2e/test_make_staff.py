"""The E2E's local-only staff role (T-9.11, D-963): a person made a moderator
or an admin, for the walk of the admin screens, which render only for staff.
Served behind T-3.13's gate, where ENV is local and the SMS is the fake's,
never in OpenAPI.

It gives staff roles only, never `user`; the change is an `audit_log` row, as
any role change is; and nothing else about the account moves."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.db import get_session
from app.core.enums import Gender, Role, UserStatus
from app.core.providers import FakeProviders
from app.main import close_resources, create_app
from app.modules.account import service as account_service
from app.modules.admin import service as admin_service
from app.modules.admin.models import AuditLogEntry
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.infra import session_for_the_app
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")


def _role(user_id: uuid.UUID) -> str:
    return f"/v1/test/users/{user_id}/role"


async def _user(db: AsyncSession, user_id: uuid.UUID) -> User:
    found = await db.scalar(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _audits(db: AsyncSession, user_id: uuid.UUID) -> list[AuditLogEntry]:
    return list(
        await db.scalars(
            select(AuditLogEntry).where(
                AuditLogEntry.target_type == "user",
                AuditLogEntry.target_id == user_id,
            )
        )
    )


@pytest.mark.parametrize("role", [Role.MODERATOR, Role.ADMIN])
async def test_makes_a_person_staff_and_audits_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, role: Role
) -> None:
    man, _ = await make_user()

    response = await client.post(_role(man.id), json={"role": role.value})

    assert response.status_code == 200, response.text
    assert response.json() == {"role": role.value}
    assert (await _user(db, man.id)).role is role
    [entry] = await _audits(db, man.id)
    assert entry.actor_id == admin_service.SYSTEM_USER_ID
    assert entry.action == "user.role"
    assert entry.meta == {"from": "user", "to": role.value, "by": "e2e"}


async def test_the_role_it_gives_opens_the_admin_api(
    client: AsyncClient, make_user: MakeUser
) -> None:
    """By its effect: the same token, refused before, is staff after, because
    `require_role` reads the account's role."""
    man, token = await make_user()
    before = await client.get("/v1/admin/metrics", headers=bearer(token))
    assert before.status_code == 403, before.text

    made = await client.post(_role(man.id), json={"role": "moderator"})
    assert made.status_code == 200, made.text

    after = await client.get("/v1/admin/metrics", headers=bearer(token))
    assert after.status_code == 200, after.text


@pytest.mark.parametrize("role", ["user", "superuser", "", "MODERATOR"])
async def test_gives_only_a_staff_role_and_changes_nothing_else(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, role: str
) -> None:
    """Never `user`: it makes staff, and nothing else, so it can't be a way to
    strip a real moderator either."""
    woman, _ = await make_user(Gender.FEMALE)

    response = await client.post(_role(woman.id), json={"role": role})

    assert response.status_code == 400, response.text
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert (await _user(db, woman.id)).role is Role.USER
    assert await _audits(db, woman.id) == []


async def test_refuses_anything_beside_the_role(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, _ = await make_user()

    response = await client.post(
        _role(man.id), json={"role": "moderator", "gender": "female"}
    )

    assert response.status_code == 400, response.text
    assert (await _user(db, man.id)).role is Role.USER


async def test_an_erased_account_is_not_found_and_unchanged(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    man_id = man.id
    # Erased by T-9.6's own anonymise, as the 30 days' erasure leaves it.
    man.status = UserStatus.DELETED
    man.deleted_requested_at = clock.now() - timedelta(days=30)
    await db.flush()
    await account_service.anonymise(db, man)
    await db.flush()

    response = await client.post(_role(man_id), json={"role": "admin"})

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert (await _user(db, man_id)).role is Role.USER
    assert await _audits(db, man_id) == []


# The route's own refusal of an id nobody holds; a missing route's 404 carries
# the framework's message instead (core/errors.py).
OWN_REFUSAL = "No such account."


async def _answer(app: FastAPI) -> Response:
    """The app's answer to a role for an id nobody holds."""
    app.dependency_overrides[get_session] = session_for_the_app
    app.state.providers = FakeProviders().as_providers()
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(_role(uuid.uuid4()), json={"role": "admin"})
    finally:
        await close_resources(app)


async def test_is_served_where_the_e2e_runs(db: AsyncSession) -> None:
    """ENV local and the fake SMS, as `tests/e2e_server.py` and CI's E2E run
    it: an unknown id is the route's own `NOT_FOUND`, not a missing route's."""
    response = await _answer(create_app(make_test_settings()))

    assert response.status_code == 404
    assert error(response)["message"] == OWN_REFUSAL


@pytest.mark.parametrize(
    "update",
    [
        # The web's build name for CI (D-085); the API has no such ENV, and a
        # gate that reads one must still refuse it.
        {"ENV": "ci"},
        {"ENV": "staging"},
        {"ENV": "production"},
        {"ENV": "preview"},
        # A name nobody has listed: a blacklist would wave it through (rule 16).
        {"ENV": "env-nobody-has-named-2031"},
        {"SMS_PROVIDER": "msg91"},
        {"ENV": "production", "SMS_PROVIDER": "fake"},
    ],
    ids=lambda update: ",".join(f"{k}={v}" for k, v in update.items()),
)
async def test_isnt_served_anywhere_else(
    db: AsyncSession, update: dict[str, str]
) -> None:
    """T-3.13's gate (D-963): local and the fake SMS, nothing else. Anywhere
    else it would let anyone make themselves an admin."""
    settings = make_test_settings().model_copy(update=update)

    response = await _answer(create_app(settings))

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert error(response)["message"] != OWN_REFUSAL


def test_is_never_in_the_schema() -> None:
    paths = create_app(make_test_settings()).openapi()["paths"]

    assert not [path for path in paths if "/role" in path and "/test" in path]
    assert not [path for path in paths if path.startswith("/v1/test")]
