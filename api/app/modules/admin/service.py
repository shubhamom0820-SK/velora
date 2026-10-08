"""Ops: tunable settings in `app_config` and the audit trail, `audit_log`
(03-SCHEMA.md §8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.modules.admin import repository

# 03-SCHEMA §8: `app_config` is cached 60 s, so a change reaches every reader
# within a minute (P-47).
CACHED_FOR: Final = timedelta(seconds=60)


class MissingConfig(Exception):
    """A setting the code needs has no row, or not the type it needs: a
    migration didn't run. A fault of ours, so it becomes a 500."""


@dataclass
class ConfigCache:
    """`app_config` values read in the last `CACHED_FOR`, one per app
    (`app.state.config_cache`), never one per process: a test that tunes a
    setting builds its own app, and would otherwise read another's (P-47)."""

    values: dict[str, tuple[int, datetime]] = field(default_factory=dict)


async def config_int(
    session: AsyncSession, key: str, *, cache: ConfigCache | None = None
) -> int:
    """An integer setting from `app_config`.

    With `cache`, read at most once a minute (P-47): the hot paths, the men's
    daily swipe cap on every swipe and discovery's radius on every page.
    Without it, fresh each time, on purpose: OTP send's daily cap, so a
    lowered cap applies at once. A missing or mistyped row is never cached.
    """
    now = clock.now()
    if cache is not None:
        held = cache.values.get(key)
        if held is not None and now - held[1] < CACHED_FOR:
            return held[0]
    value = await repository.config_value(session, key)
    if type(value) is not int:  # not a bool, which is an int too
        raise MissingConfig(f"app_config has no integer {key!r}")
    if cache is not None:
        cache.values[key] = (value, now)
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
