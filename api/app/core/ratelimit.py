"""Sliding-window rate limits in Redis (02-ARCHITECTURE.md §12).

One sorted set per scope and client: each allowed request is a member, scored by
its time in milliseconds. A request is allowed while fewer than `limit` members
fall inside the last `window_s` seconds. Only allowed requests are recorded, so
a client that keeps knocking on a closed window doesn't push its own reopening
further away, and `retry_after_s` stays honest.

The check and the write are one Lua script, so two requests racing on two
workers can't both take the last place. Time comes from `clock.now()`, passed
in, so tests can freeze and advance it; Redis's own clock only expires the key.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import ceil

from redis.asyncio import Redis

from app.core import clock

KEY_PREFIX = "ratelimit:"

# KEYS[1] the window; ARGV now (ms), window (ms), limit, a unique member.
# Returns {1, 0} when allowed, {0, ms until the oldest entry leaves} when not.
_HIT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now_ms, ARGV[4])
  redis.call('PEXPIRE', key, window_ms)
  return {1, 0}
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
return {0, tonumber(oldest[2]) + window_ms - now_ms}
"""


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    # Whole seconds until a request would be allowed: 0 when it is, else 1 or more.
    retry_after_s: int


def key_for(scope: str, bucket: str) -> str:
    return f"{KEY_PREFIX}{scope}:{bucket}"


async def hit(
    redis: Redis, scope: str, bucket: str, *, limit: int, window_s: int
) -> Verdict:
    """Count one request from `bucket` against `scope`'s limit, if there's room."""
    now_ms = int(clock.now().timestamp() * 1000)
    window_ms = window_s * 1000
    script = redis.register_script(_HIT)
    allowed, wait_ms = await script(
        keys=[key_for(scope, bucket)],
        # The member only has to be unique: two requests in one millisecond
        # must be two entries, not one.
        args=[now_ms, window_ms, limit, f"{now_ms}:{uuid.uuid4().hex}"],
    )
    if int(allowed) == 1:
        return Verdict(allowed=True, retry_after_s=0)
    return Verdict(allowed=False, retry_after_s=max(1, ceil(int(wait_ms) / 1000)))


# KEYS[1] the window; ARGV now (ms), window (ms), limit. Like _HIT, but records
# nothing: {1, 0} when a hit would be allowed, {0, ms until it would be} if not.
_PEEK = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
if redis.call('ZCARD', key) < limit then
  return {1, 0}
end
local oldest = redis.call('ZRANGE', key, -limit, -limit, 'WITHSCORES')
return {0, tonumber(oldest[2]) + window_ms - now_ms}
"""


async def peek(
    redis: Redis, scope: str, bucket: str, *, limit: int, window_s: int
) -> Verdict:
    """Whether `bucket` has room under `scope`'s limit, recording nothing.

    For a count kept by one route and enforced by another: verify records each
    wrong sign-in code with `hit`, and send refuses a phone at the limit with
    this (D-066). When it's full, the wait is until enough entries leave for a
    place to open: the limit-th newest, not the oldest, if a window ever holds
    more than `limit`.
    """
    now_ms = int(clock.now().timestamp() * 1000)
    script = redis.register_script(_PEEK)
    allowed, wait_ms = await script(
        keys=[key_for(scope, bucket)], args=[now_ms, window_s * 1000, limit]
    )
    if int(allowed) == 1:
        return Verdict(allowed=True, retry_after_s=0)
    return Verdict(allowed=False, retry_after_s=max(1, ceil(int(wait_ms) / 1000)))


async def used(redis: Redis, scope: str, bucket: str, *, window_s: int) -> int:
    """How many hits `bucket` has inside `scope`'s window now."""
    now_ms = int(clock.now().timestamp() * 1000)
    count = await redis.zcount(
        key_for(scope, bucket), now_ms - window_s * 1000 + 1, "+inf"
    )
    return int(count)
