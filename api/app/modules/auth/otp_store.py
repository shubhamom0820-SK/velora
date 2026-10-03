"""Sign-in codes in Redis, Path B (D-063, D-066).

- `otp:code:{phone_hash}`: the code's keyed HMAC (`h`), wrong tries so far
  (`a`) and when it expires, in ms (`x`). The expiry is read against
  `core.clock` (T-3.3), so tests can move it; Redis's own TTL only clears the
  key away afterwards.
- `otp:sent:{IST date}`: how many codes the API has sent today, for the global
  daily cap.

Rate-limit windows (resend, per phone, wrong codes) live in `core.ratelimit`.
Keys carry the number's hash, never the number, and no value is a code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from redis.asyncio import Redis

KEY_PREFIX = "otp:"
# A day's count outlives its day, so a send just before midnight IST still
# finds it; two days is ample.
_SENT_TTL_S = 2 * 24 * 60 * 60


@dataclass(frozen=True)
class StoredCode:
    code_hash: str
    attempts: int
    expires_at_ms: int


def code_key(phone_hash: str) -> str:
    return f"{KEY_PREFIX}code:{phone_hash}"


def sent_key(day: date) -> str:
    return f"{KEY_PREFIX}sent:{day.isoformat()}"


async def save_code(
    redis: Redis, phone_hash: str, code_hash: str, *, expires_at: datetime, ttl_s: int
) -> None:
    """Replace any code this number had with a new one, at 0 wrong tries."""
    key = code_key(phone_hash)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(key)
        pipe.hset(
            key,
            mapping={
                "h": code_hash,
                "a": 0,
                "x": int(expires_at.timestamp() * 1000),
            },
        )
        pipe.expire(key, ttl_s)
        await pipe.execute()


async def read_code(redis: Redis, phone_hash: str) -> StoredCode | None:
    # redis-py types the asyncio client's hash commands as maybe-sync.
    fields: dict[bytes, bytes] = await redis.hgetall(code_key(phone_hash))  # type: ignore[misc]
    if not fields:
        return None
    return StoredCode(
        code_hash=fields[b"h"].decode(),
        attempts=int(fields[b"a"]),
        expires_at_ms=int(fields[b"x"]),
    )


async def discard_code(redis: Redis, phone_hash: str) -> None:
    await redis.delete(code_key(phone_hash))


# KEYS[1] the code; ARGV[1] the hash the caller checked. Deletes the code only if
# it is still that one, so of two requests presenting the right code at once,
# one signs in and the other finds it gone; and a code a resend replaced in the
# meantime is never consumed by the old one.
_CONSUME = """
if redis.call('HGET', KEYS[1], 'h') == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

# KEYS[1] the code. One more wrong try, unless the code has gone (expired,
# consumed or replaced): then -1, and nothing is created.
_WRONG_TRY = """
if redis.call('EXISTS', KEYS[1]) == 1 then
  return redis.call('HINCRBY', KEYS[1], 'a', 1)
end
return -1
"""


async def consume_code(redis: Redis, phone_hash: str, code_hash: str) -> bool:
    """Use the code up, if it is still `code_hash`. True for exactly one caller."""
    script = redis.register_script(_CONSUME)
    return int(await script(keys=[code_key(phone_hash)], args=[code_hash])) == 1


async def add_wrong_try(redis: Redis, phone_hash: str) -> int | None:
    """The code's wrong tries after this one, or None if the code has gone."""
    script = redis.register_script(_WRONG_TRY)
    tries = int(await script(keys=[code_key(phone_hash)]))
    return None if tries < 0 else tries


async def count_send(redis: Redis, day: date) -> int:
    """Count one more code sent on `day` and return the day's total."""
    key = sent_key(day)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, _SENT_TTL_S)
        sent, _ = await pipe.execute()
    return int(sent)
