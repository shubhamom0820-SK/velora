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
    session: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    meta: dict[str, Any] | None,
    target: tuple[str, UUID] | None = None,
) -> UUID:
    target_type, target_id = target if target is not None else (None, None)
    added = await session.scalar(
        insert(AuditLogEntry)
        .values(
            actor_id=actor_id,
            action=action,
            meta=meta,
            target_type=target_type,
            target_id=target_id,
        )
        .returning(AuditLogEntry.id)
    )
    assert added is not None  # an insert returns its row
    return added
