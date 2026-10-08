"""Ops: tunable settings in `app_config` and the audit trail, `audit_log`
(03-SCHEMA.md §8)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin import repository


class MissingConfig(Exception):
    """A setting the code needs has no row, or not the type it needs: a
    migration didn't run. A fault of ours, so it becomes a 500."""


async def config_int(session: AsyncSession, key: str) -> int:
    """An integer setting from `app_config`, read fresh each time.

    Not cached yet: its first reader, OTP send's daily cap, is rate-limited and
    reads one row by primary key. The 60 s cache the model describes arrives
    with a hot path (P-47).
    """
    value = await repository.config_value(session, key)
    if type(value) is not int:  # not a bool, which is an int too
        raise MissingConfig(f"app_config has no integer {key!r}")
    return value


async def audit(
    session: AsyncSession,
    actor_id: UUID,
    action: str,
    meta: dict[str, Any] | None = None,
) -> None:
    """Record an admin's call in `audit_log`, inside the caller's transaction,
    beside whatever it did or read (02-ARCHITECTURE §12, T-9.5's "every call")."""
    await repository.add_audit(session, actor_id=actor_id, action=action, meta=meta)
