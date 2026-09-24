"""Redis client and the readiness check.

One async client per process, created lazily from `REDIS_URL` for the same
reason as the database engine: code that never runs the app's lifespan still
gets a working client. The lifespan closes it on shutdown.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """The process-wide client, created on first use."""
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().REDIS_URL)
    return _client


async def close_redis() -> None:
    """Close the connection pool. Safe to call when no client exists."""
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def check_redis() -> None:
    """Raise if Redis does not answer `PING`. Used only by `/readyz`."""
    await get_redis().ping()
