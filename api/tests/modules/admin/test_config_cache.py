"""P-47: `app_config` cached 60 s per app. Within the minute a reader with the
cache gets what it read; after it, the row as it is now; without the cache,
always the row. Two apps never share one, and a missing or mistyped row is
never cached."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.modules.admin.service import CACHED_FOR, ConfigCache, MissingConfig, config_int
from tests.conftest import make_test_settings

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)
KEY = "swipe_daily_limit_men"


async def _set(db: AsyncSession, key: str, value: str) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:value AS jsonb) WHERE key = :key"),
        {"key": key, "value": value},
    )


async def test_the_cache_holds_a_value_for_a_minute_then_reads_again(
    db: AsyncSession, clock: ModuleType
) -> None:
    assert CACHED_FOR == timedelta(seconds=60)
    clock.freeze(NOON)
    cache = ConfigCache()
    assert await config_int(db, KEY, cache=cache) == 50

    await _set(db, KEY, "30")
    clock.advance(timedelta(seconds=59, microseconds=999_999))
    assert await config_int(db, KEY, cache=cache) == 50
    clock.advance(timedelta(microseconds=1))

    assert await config_int(db, KEY, cache=cache) == 30


async def test_without_the_cache_it_is_always_the_row(
    db: AsyncSession, clock: ModuleType
) -> None:
    """OTP send's daily cap reads this way, so a lowered cap applies at once."""
    clock.freeze(NOON)
    assert await config_int(db, KEY) == 50

    await _set(db, KEY, "30")

    assert await config_int(db, KEY) == 30


async def test_two_caches_never_share_a_value(
    db: AsyncSession, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    first, second = ConfigCache(), ConfigCache()
    assert await config_int(db, KEY, cache=first) == 50

    await _set(db, KEY, "30")

    assert await config_int(db, KEY, cache=second) == 30
    assert await config_int(db, KEY, cache=first) == 50


def test_each_app_has_a_cache_of_its_own() -> None:
    """Per app, never per process (P-47): a test that tunes a setting builds
    its own app, and must never read another app's value."""
    one, two = create_app(make_test_settings()), create_app(make_test_settings())

    assert isinstance(one.state.config_cache, ConfigCache)
    assert one.state.config_cache is not two.state.config_cache


@pytest.mark.parametrize("value", ["true", '"50"', "null"])
async def test_a_row_that_isnt_an_integer_is_refused_and_never_cached(
    db: AsyncSession, clock: ModuleType, value: str
) -> None:
    clock.freeze(NOON)
    cache = ConfigCache()
    await _set(db, KEY, value)

    with pytest.raises(MissingConfig):
        await config_int(db, KEY, cache=cache)

    assert cache.values == {}
    await _set(db, KEY, "40")
    assert await config_int(db, KEY, cache=cache) == 40


async def test_a_missing_row_is_refused_and_never_cached(db: AsyncSession) -> None:
    cache = ConfigCache()

    with pytest.raises(MissingConfig):
        await config_int(db, "no_such_setting", cache=cache)

    assert cache.values == {}
