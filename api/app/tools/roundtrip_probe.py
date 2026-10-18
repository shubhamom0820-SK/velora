"""P-49's measurement: what a round trip to Postgres and to Redis costs from
where the API runs, through the app's own engine and Redis client.

It prints numbers only, in milliseconds, and the address family each host was
reached over (AF_INET6 for Supabase's direct host), never a host, a URL or a
value. In order: a TCP connect to each host; opening a database connection
(TCP, TLS, authentication and asyncpg's first queries); `SELECT 1` on a warm
connection, many times; and Redis `PING`, many times, which Upstash doesn't
charge for (D-091). Medians and 95th percentiles, since one reading is noise.

Runs only where ENV is local or staging (rule 16), with the settings the
container already has. On the staging VM, behind IAP:

    gcloud compute ssh velora-api-staging --project=velora-ic-staging \\
      --zone=asia-south1-a --tunnel-through-iap --command \\
      "sudo docker compose -p velora exec -T api python -m app.tools.roundtrip_probe"

Exit 0 when every measurement ran, 1 when one failed (named, never with its
message, which can carry a host), 2 when it may not run here.
"""

from __future__ import annotations

import asyncio
import socket
import statistics
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Final, TextIO
from urllib.parse import urlsplit

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import build_engine
from app.core.redis import build_redis

PROBE_RUNS_IN: Final = frozenset({"local", "staging"})
QUERIES: Final = 50
CONNECTS: Final = 5
WARMUP: Final = 3


def _ms(seconds: float) -> str:
    return f"{seconds * 1000:.1f} ms"


def summary(samples: list[float]) -> str:
    """Median and 95th percentile, and how many readings they come from."""
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return (
        f"median {_ms(statistics.median(ordered))}, p95 {_ms(p95)}, over {len(ordered)}"
    )


async def _timed(step: Callable[[], Awaitable[object]]) -> float:
    started = time.perf_counter()
    await step()
    return time.perf_counter() - started


async def tcp_connect(url: str, default_port: int) -> tuple[float, str]:
    """One TCP connect to the URL's host, and the family it went over."""
    parts = urlsplit(url)
    started = time.perf_counter()
    reader, writer = await asyncio.open_connection(
        parts.hostname, parts.port or default_port
    )
    took = time.perf_counter() - started
    family = socket.AddressFamily(writer.get_extra_info("socket").family).name
    writer.close()
    await writer.wait_closed()
    del reader
    return took, family


async def measure(
    database_url: str,
    redis_url: str,
    *,
    out: TextIO,
    queries: int = QUERIES,
    connects: int = CONNECTS,
) -> int:
    failed = 0

    for name, url, port in (
        ("postgres", database_url, 5432),
        ("redis", redis_url, 6379),
    ):
        try:
            took, family = await tcp_connect(url, port)
            out.write(f"{name} tcp connect: {_ms(took)} ({family})\n")
        except OSError as error:
            out.write(f"{name} tcp connect: FAILED ({type(error).__name__})\n")
            failed = 1

    try:
        opens: list[float] = []
        for _ in range(connects):
            engine = build_engine(
                database_url, pool_size=1, max_overflow=0, hide_parameters=True
            )
            try:
                started = time.perf_counter()
                async with engine.connect() as conn:
                    opens.append(time.perf_counter() - started)
                    await conn.execute(text("SELECT 1"))
            finally:
                await engine.dispose()
        out.write(f"postgres connection opened: {summary(opens)}\n")

        engine = build_engine(
            database_url, pool_size=1, max_overflow=0, hide_parameters=True
        )
        try:
            async with engine.connect() as conn:
                select = text("SELECT 1")
                for _ in range(WARMUP):
                    await conn.execute(select)
                trips = [
                    await _timed(lambda: conn.execute(select)) for _ in range(queries)
                ]
        finally:
            await engine.dispose()
        out.write(f"postgres SELECT 1, warm connection: {summary(trips)}\n")
    except Exception as error:  # noqa: BLE001 — named, never its message (a host)
        out.write(f"postgres: FAILED ({type(error).__name__})\n")
        failed = 1

    redis = build_redis(redis_url)
    try:
        for _ in range(WARMUP):
            await redis.ping()
        pings = [await _timed(redis.ping) for _ in range(queries)]
        out.write(f"redis PING: {summary(pings)}\n")
    except Exception as error:  # noqa: BLE001 — named, never its message (a host)
        out.write(f"redis: FAILED ({type(error).__name__})\n")
        failed = 1
    finally:
        await redis.aclose()

    return failed


def main(out: TextIO = sys.stdout) -> int:
    settings = get_settings()
    if settings.ENV not in PROBE_RUNS_IN:
        out.write(
            f"roundtrip_probe: refused, ENV={settings.ENV} (only local and staging)\n"
        )
        return 2
    return asyncio.run(measure(settings.DATABASE_URL, settings.REDIS_URL, out=out))


if __name__ == "__main__":
    raise SystemExit(main())
