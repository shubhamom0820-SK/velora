"""A woman's two daily limits (D-098; T-7.1, T-7.3), in Redis, by the IST day.

- **New men:** at most `women_new_men_daily_limit` (30) different men a day
  that she opens a Thread with or writes to first. A set of their ids, so the
  same man twice in a day counts once.
- **Private messages:** at most `women_private_messages_daily_limit` (30) of
  her messages a day in private-message Threads. A counter.

Limits, never prices: she is never charged (D-098). Past either, the request
is `RATE_LIMITED`, until the next IST midnight. A place is taken before the
transaction and given back if nothing is written, as swipes' cap is (T-6.4).
Each take is one Lua script, so two requests at once can't both take the last
place. A key outlives its day by a day and then goes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import ceil
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from app.core import clock
from app.core.clock import IST
from app.core.enums import Gender
from app.core.errors import AppError

NEW_MEN_KEY: Final = "women_new_men_daily_limit"
PRIVATE_MESSAGES_KEY: Final = "women_private_messages_daily_limit"
KEPT_FOR_S: Final = 2 * 24 * 3600

# KEYS[1] the day's set; ARGV the man, the limit, the key's lifetime.
# 1 when he was added, 0 when he was already counted today, -1 when full.
_TAKE_MAN = """
if redis.call('SISMEMBER', KEYS[1], ARGV[1]) == 1 then return 0 end
if redis.call('SCARD', KEYS[1]) >= tonumber(ARGV[2]) then return -1 end
redis.call('SADD', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
return 1
"""

# KEYS[1] the day's counter; ARGV the limit, the key's lifetime.
# 1 when a place was taken, -1 when none was left.
_TAKE_MESSAGE = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
if used >= tonumber(ARGV[1]) then return -1 end
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
return 1
"""


def limited(gender: Gender | None) -> bool:
    """Whether these limits apply at all: to a woman only."""
    return gender is Gender.FEMALE


def counts_as_a_man(gender: Gender | None) -> bool:
    """Whether the other person is one of "30 men" (D-098)."""
    return gender is Gender.MALE


def _men_key(user_id: UUID, day: date) -> str:
    return f"women:new_men:{user_id}:{day.isoformat()}"


def _messages_key(user_id: UUID, day: date) -> str:
    return f"women:private_messages:{user_id}:{day.isoformat()}"


def _limit_reached(day: date) -> AppError:
    resets = datetime.combine(day + timedelta(days=1), time(0), tzinfo=IST)
    wait = max(1, ceil((resets - clock.now()).total_seconds()))
    return AppError(
        "RATE_LIMITED",
        "That's today's limit. More tomorrow.",
        status=429,
        details={"retry_after_s": wait},
    )


async def take_new_man(
    redis: Redis, user_id: UUID, man_id: UUID, day: date, limit: int
) -> bool:
    """Count `man_id` among today's new men: True when this took a place,
    False when he was already counted today. Full: `RATE_LIMITED`."""
    taken = int(
        await redis.eval(  # type: ignore[misc]
            _TAKE_MAN,
            1,
            _men_key(user_id, day),
            str(man_id),
            str(limit),
            str(KEPT_FOR_S),
        )
    )
    if taken < 0:
        raise _limit_reached(day)
    return taken == 1


async def give_back_new_man(
    redis: Redis, user_id: UUID, man_id: UUID, day: date
) -> None:
    await redis.srem(_men_key(user_id, day), str(man_id))  # type: ignore[misc]


async def take_private_message(
    redis: Redis, user_id: UUID, day: date, limit: int
) -> None:
    """Take one of today's private-message places, or `RATE_LIMITED`."""
    taken = int(
        await redis.eval(  # type: ignore[misc]
            _TAKE_MESSAGE, 1, _messages_key(user_id, day), str(limit), str(KEPT_FOR_S)
        )
    )
    if taken < 0:
        raise _limit_reached(day)


async def give_back_private_message(redis: Redis, user_id: UUID, day: date) -> None:
    await redis.decr(_messages_key(user_id, day))


class Taken:
    """The places one request took, to give back if it writes nothing."""

    def __init__(self, redis: Redis, user_id: UUID, day: date) -> None:
        self._redis = redis
        self._user_id = user_id
        self._day = day
        self._man: UUID | None = None
        self._message = False

    async def new_man(self, man_id: UUID, limit: int) -> None:
        if await take_new_man(self._redis, self._user_id, man_id, self._day, limit):
            self._man = man_id

    async def private_message(self, limit: int) -> None:
        await take_private_message(self._redis, self._user_id, self._day, limit)
        self._message = True

    async def give_back(self) -> None:
        if self._man is not None:
            await give_back_new_man(self._redis, self._user_id, self._man, self._day)
            self._man = None
        if self._message:
            await give_back_private_message(self._redis, self._user_id, self._day)
            self._message = False
