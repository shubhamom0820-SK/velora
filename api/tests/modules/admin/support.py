"""What the panel's tests share (T-9.5): staff to call it, and its record."""

from __future__ import annotations

import uuid
from typing import Any

from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, Role
from app.modules.admin.models import AuditLogEntry
from tests.conftest import MakeUser

ADMIN = "/v1/admin"
REASON = "Checked against the report and the chat."


async def staff(
    make_user: MakeUser, role: Role = Role.ADMIN, gender: Gender = Gender.FEMALE
) -> tuple[uuid.UUID, str]:
    """A moderator or an admin, signed in: their id and token. A woman, so no
    wallet of hers is ever in play. An id, never the row: a request commits
    the test's session, which expires every row it holds."""
    person, token = await make_user(gender)
    person.role = role
    return person.id, token


def auth(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def audits(
    db: AsyncSession, actor_id: uuid.UUID, action: str | None = None
) -> list[AuditLogEntry]:
    """What `actor_id` did, oldest first, fresh from the database."""
    query = (
        select(AuditLogEntry)
        .where(AuditLogEntry.actor_id == actor_id)
        .order_by(AuditLogEntry.created_at, AuditLogEntry.id)
        .execution_options(populate_existing=True)
    )
    if action is not None:
        query = query.where(AuditLogEntry.action == action)
    return list(await db.scalars(query))


async def fresh(db: AsyncSession, model: Any, row_id: Any) -> Any:
    """A row re-read from the database, never the session's copy."""
    found = await db.scalar(
        select(model)
        .where(model.id == row_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found
