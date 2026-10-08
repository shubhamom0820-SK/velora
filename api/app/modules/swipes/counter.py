"""Men's daily swipe count (T-6.4), in Redis, one key per man per IST day.

A swipe takes a place before its transaction starts and gives it back if the
swipe isn't written (a duplicate, a refusal, nobody to swipe), so the count is
of swipes made. INCR is atomic, so two swipes at once can't both take the last
place. The key outlives its day by a day and then goes; nothing reads it after.
"""

from __future__ import annotations

from datetime import date
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

KEY_PREFIX: Final = "swipes:"
KEPT_FOR_S: Final = 2 * 24 * 3600


def key_for(user_id: UUID, day: date) -> str:
    return f"{KEY_PREFIX}{user_id}:{day.isoformat()}"


async def take(redis: Redis, user_id: UUID, day: date, limit: int) -> int | None:
    """Take one of today's `limit` places: the count with it taken, or None,
    having taken nothing, when every place is gone."""
    key = key_for(user_id, day)
    used = int(await redis.incr(key))
    if used == 1:
        await redis.expire(key, KEPT_FOR_S)
    if used > limit:
        await redis.decr(key)
        return None
    return used


async def give_back(redis: Redis, user_id: UUID, day: date) -> None:
    """Return a place `take` gave, for a swipe that wasn't written."""
    await redis.decr(key_for(user_id, day))


async def used(redis: Redis, user_id: UUID, day: date) -> int:
    value = await redis.get(key_for(user_id, day))
    return 0 if value is None else int(value)
