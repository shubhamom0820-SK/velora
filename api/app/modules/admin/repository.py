"""SQL for the ops tables. No rules here: the services decide."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import AppConfig, AuditLogEntry


async def config_value(session: AsyncSession, key: str) -> Any | None:
    """`app_config.value` for `key`, decoded from JSON, or None if no row."""
    return await session.scalar(select(AppConfig.value).where(AppConfig.key == key))


async def add_audit(
    session: AsyncSession, *, actor_id: UUID, action: str, meta: dict[str, Any] | None
) -> None:
    await session.execute(
        insert(AuditLogEntry).values(actor_id=actor_id, action=action, meta=meta)
    )
