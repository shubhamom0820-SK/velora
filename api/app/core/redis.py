"""Redis client and the readiness check.

Each app owns its client, built by `create_app()` from the app's own settings and
kept on `app.state` — for the same reason as the database engine (P-05). Building
the client opens no connection; the first command does.
"""

from __future__ import annotations

from redis.asyncio import Redis


def build_redis(url: str) -> Redis:
    client: Redis = Redis.from_url(url)  # from_url is typed as Any upstream
    return client


async def check_redis(client: Redis) -> None:
    """Raise if Redis does not answer `PING`. Used only by `/readyz`."""
    await client.ping()
