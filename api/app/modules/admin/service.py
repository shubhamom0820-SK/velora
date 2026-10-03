"""Ops: tunable settings in `app_config` (03-SCHEMA.md §8)."""

from __future__ import annotations

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
