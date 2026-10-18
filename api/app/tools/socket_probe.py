"""P-49's socket check: a real WebSocket through the public hostname, opened
with a real ticket, and answered.

It makes a ticket for one account (`realtime.service.issue`: 30 seconds, single
use), opens `<URL>/ws?ticket=…` with the web's Origin (the first of
CORS_ORIGINS), sends `ping`, and waits for `pong`, as the web does. So it proves
the whole path a browser takes: DNS, TLS, Caddy's upgrade, the API's Origin and
ticket checks, the socket's reply. It prints what happened and how long it took;
never the ticket, the URL it was in, or a host from an error.

Runs only where ENV is local or staging (rule 16), inside the API's container,
so the ticket never leaves the process that made it. On the staging VM:

    sudo docker compose -p velora exec -T api python -m app.tools.socket_probe \\
      --user <a test account's id> --url wss://api.staging.veloraapp.co.in

Exit 0 when the socket opened and answered, 1 when it didn't (named), 2 when it
may not run here or was called wrongly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from collections.abc import Sequence
from typing import Final, TextIO

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.core.config import get_settings
from app.core.redis import build_redis
from app.modules.realtime import service

PROBE_RUNS_IN: Final = frozenset({"local", "staging"})
TIMEOUT_S: Final = 10.0


def parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.tools.socket_probe")
    parser.add_argument(
        "--user", required=True, type=uuid.UUID, help="the account's id"
    )
    parser.add_argument("--url", required=True, help="the API's base, ws:// or wss://")
    return parser.parse_args(argv)


async def probe(base: str, *, ticket: str, origin: str, out: TextIO) -> int:
    """Open the socket with `ticket`, ping, and wait for the pong."""
    started = time.perf_counter()
    try:
        async with connect(
            f"{base.rstrip('/')}/ws?ticket={ticket}",
            origin=origin,  # type: ignore[arg-type]  # a str is what the header takes
            open_timeout=TIMEOUT_S,
        ) as socket:
            opened = time.perf_counter()
            out.write(f"socket opened in {(opened - started) * 1000:.0f} ms\n")
            await socket.send(json.dumps({"type": "ping"}))
            while True:
                raw = await asyncio.wait_for(socket.recv(), timeout=TIMEOUT_S)
                kind = json.loads(raw).get("type")
                if kind == "pong":
                    out.write(
                        f"pong in {(time.perf_counter() - opened) * 1000:.0f} ms\n"
                    )
                    return 0
                out.write(f"an event first: {kind}\n")
    except InvalidStatus as refused:
        out.write(f"refused at the handshake: HTTP {refused.response.status_code}\n")
    except ConnectionClosed as closed:
        code = closed.rcvd.code if closed.rcvd else "none"
        out.write(f"closed before a pong: code {code}\n")
    except TimeoutError:
        out.write(f"no answer within {TIMEOUT_S:.0f} s\n")
    except Exception as error:  # noqa: BLE001 — named, never its message (a host, the ticket)
        out.write(f"failed: {type(error).__name__}\n")
    return 1


async def run(args: argparse.Namespace, out: TextIO) -> int:
    settings = get_settings()
    if settings.ENV not in PROBE_RUNS_IN:
        out.write(
            f"socket_probe: refused, ENV={settings.ENV} (only local and staging)\n"
        )
        return 2
    if not args.url.startswith(("ws://", "wss://")):
        out.write("socket_probe: --url must start with ws:// or wss://\n")
        return 2
    redis = build_redis(settings.REDIS_URL)
    try:
        ticket = await service.issue(redis, args.user)
    finally:
        await redis.aclose()
    return await probe(
        args.url, ticket=ticket, origin=settings.CORS_ORIGINS[0], out=out
    )


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    return asyncio.run(run(parse(sys.argv[1:] if argv is None else argv), out))


if __name__ == "__main__":
    raise SystemExit(main())
