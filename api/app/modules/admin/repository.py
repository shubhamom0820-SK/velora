"""SQL for the ops tables. No rules here: the services decide."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import AppConfig


async def config_value(session: AsyncSession, key: str) -> Any | None:
    """`app_config.value` for `key`, decoded from JSON, or None if no row."""
    return await session.scalar(select(AppConfig.value).where(AppConfig.key == key))
