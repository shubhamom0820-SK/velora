"""1,000 sockets on one API process, under 256 MB (T-7.4's load test).

    uv run python -m bench.realtime.sockets                # from api/, `make infra-up` first
    uv run python -m bench.realtime.sockets --count 1000 --hold 10

Run by hand, never in `make test` or CI (a measure on a shared runner proves
nothing about ours, and fails at random), and on the local stack only: it
refuses unless `ENV` is `local` (rule 16).

It starts the API itself, `uvicorn app.main:app` on a free loopback port, as
`make dev` runs it, so the process measured is the API alone. Then it writes
`count` tickets straight into Redis, for made-up users (the gateway reads no
database, so none need exist), opens a socket on each from the web's own
origin, publishes one event to every user and counts what arrives, and reads
the server's resident memory (`ps -o rss`) idle, with every socket open, and
after every event. It writes all of it to `out/t-7.4-bench/`, git-ignored.

Exit 1 if a socket failed to open, an event didn't arrive, or the memory, with
every socket open or after every event, reached 256 MB. Measured on this
machine, never Fly's: the number says what one process of ours holds, not
what Fly's machine reports.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import socket as socketlib
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Final

import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.typing import Origin

from app.core import clock, events
from app.core.config import get_settings
from app.core.redis import build_redis
from app.modules.realtime import service

LIMIT_MB: Final = 256
API_DIR: Final = Path(__file__).resolve().parents[2]
OUT: Final = API_DIR.parent / "out" / "t-7.4-bench"
# Sockets opened at once: a crowd arriving, not a single burst of a thousand.
OPENING_AT_ONCE: Final = 100
EVENT: Final = "bench.ping"


def rss_mb(pid: int) -> float:
    """Resident memory of `pid` in MB, as `ps` reports it (KB on macOS and Linux)."""
    out = subprocess.run(  # its output is read below
        ["ps", "-o", "rss=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return int(out.strip()) / 1024


def verdict(count: int, opened: int, delivered: int, peak_mb: float) -> list[str]:
    """Why the run failed, or nothing. `peak_mb`: the most the server held,
    with every socket open or after every event."""
    failures = []
    if opened != count:
        failures.append(f"{count - opened} of {count} sockets didn't open")
    if delivered != count:
        failures.append(f"{count - delivered} of {count} events didn't arrive")
    if peak_mb >= LIMIT_MB:
        failures.append(f"{peak_mb:.1f} MB at most, not under {LIMIT_MB}")
    return failures


def _free_port() -> int:
    with socketlib.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _raise_open_files(needed: int) -> None:
    """Each socket is a file on both sides; macOS starts a shell at 256."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    want = min(hard, max(soft, needed))
    resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
    if want < needed:
        raise SystemExit(f"open files capped at {want}; {needed} needed")


def _start_api(port: int) -> subprocess.Popen[bytes]:
    """The API alone, as `make dev` runs it, on a loopback port of its own."""
    return subprocess.Popen(  # stopped by the caller
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=API_DIR,
        env={**os.environ},
    )


async def _wait_ready(base: str) -> None:
    async with httpx.AsyncClient() as client:
        for _ in range(100):
            try:
                if (await client.get(f"{base}/healthz")).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.2)
    raise SystemExit("the API didn't start")


async def _open(
    url: str, origin: str, gate: asyncio.Semaphore
) -> ClientConnection | None:
    async with gate:
        try:
            return await connect(url, origin=Origin(origin), open_timeout=30)
        except Exception:  # noqa: BLE001 — counted, not raised
            return None


async def _one_event(conn: ClientConnection) -> bool:
    try:
        raw = await asyncio.wait_for(conn.recv(), timeout=30)
    except Exception:  # noqa: BLE001 — counted, not raised
        return False
    return bool(json.loads(raw).get("type") == EVENT)


async def run(count: int, hold: float) -> dict[str, Any]:
    settings = get_settings()
    if settings.ENV not in ("local",):
        raise SystemExit(f"ENV is {settings.ENV!r}: this runs on the local stack only")
    origin = settings.CORS_ORIGINS[0]
    _raise_open_files(2 * count + 200)
    port = _free_port()
    server = _start_api(port)
    redis = build_redis(settings.REDIS_URL)
    conns: list[ClientConnection] = []
    try:
        await _wait_ready(f"http://127.0.0.1:{port}")
        idle_mb = rss_mb(server.pid)
        users = [uuid.uuid4() for _ in range(count)]
        tickets = [await service.issue(redis, user) for user in users]
        gate = asyncio.Semaphore(OPENING_AT_ONCE)
        started = time.monotonic()
        opened = await asyncio.gather(
            *(
                _open(f"ws://127.0.0.1:{port}/ws?ticket={ticket}", origin, gate)
                for ticket in tickets
            )
        )
        conns = [conn for conn in opened if conn is not None]
        open_s = time.monotonic() - started
        await asyncio.sleep(hold)
        open_mb = rss_mb(server.pid)
        pending = [asyncio.ensure_future(_one_event(conn)) for conn in conns]
        # Published here one by one: `events.publish` gives a request's few
        # events 1 s in all, and a thousand can outrun that.
        for user in users:
            await redis.publish(
                f"user:{user}", events.Event(user, EVENT, {}).envelope()
            )
        arrived = await asyncio.gather(*pending)
        after_mb = rss_mb(server.pid)
    finally:
        for conn in conns:
            await conn.close()
        await redis.aclose()
        server.terminate()
        server.wait(timeout=30)
    delivered = sum(arrived)
    return {
        "measured_at": clock.now().isoformat(),
        "count": count,
        "opened": len(conns),
        "delivered": delivered,
        "open_seconds": round(open_s, 2),
        "idle_mb": round(idle_mb, 1),
        "open_mb": round(open_mb, 1),
        "after_events_mb": round(after_mb, 1),
        "limit_mb": LIMIT_MB,
        "failures": verdict(count, len(conns), delivered, max(open_mb, after_mb)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument(
        "--hold", type=float, default=5.0, help="seconds open before measuring"
    )
    args = parser.parse_args()
    result = asyncio.run(run(args.count, args.hold))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"sockets-{result['measured_at'][:19].replace(':', '')}.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(f"written to {path}\n")
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
