"""Firebase ID tokens already exchanged, in Redis, Path A (D-085).

- `firebase:used:{sha256 of the token}`: present once a token has signed in,
  until the token would have expired anyway. Firebase ID tokens carry no `jti`,
  so the token's hash stands in: it names the token without keeping it.

No key or value is the token itself, or the number it was for (rule 15).
"""

from __future__ import annotations

from redis.asyncio import Redis

KEY_PREFIX = "firebase:"


def used_key(token_hash: str) -> str:
    return f"{KEY_PREFIX}used:{token_hash}"


async def spend(redis: Redis, token_hash: str, *, ttl_s: int) -> bool:
    """Mark the token used, for `ttl_s` seconds. True the first time, False for
    every time after: one atomic SET NX, so two requests racing with the same
    token can't both win."""
    return bool(await redis.set(used_key(token_hash), "1", nx=True, ex=max(1, ttl_s)))
