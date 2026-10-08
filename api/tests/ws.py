"""A WebSocket client for tests, in process (T-7.4): the app is called as
ASGI, on the test's own event loop, so it shares the `db` fixture and Redis
as `client` does, and needs no server and no library.

    async with connect(app, "/ws?ticket=…", origin=ORIGIN) as ws:
        await ws.send({"type": "ping"})
        envelope = await ws.receive()
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI

TIMEOUT_S = 2.0


class Refused(Exception):
    """The handshake was refused; `code` is the close code the app gave."""

    def __init__(self, code: int) -> None:
        super().__init__(f"refused with {code}")
        self.code = code


class Closed(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"closed with {code}")
        self.code = code


class TestSocket:
    def __init__(
        self,
        inbox: asyncio.Queue[MutableMapping[str, Any]],
        outbox: asyncio.Queue[MutableMapping[str, Any]],
    ) -> None:
        self._to_app = inbox
        self._from_app = outbox

    async def send(self, envelope: dict[str, Any]) -> None:
        await self._to_app.put(
            {"type": "websocket.receive", "text": json.dumps(envelope)}
        )

    async def receive(self, timeout: float = TIMEOUT_S) -> dict[str, Any]:
        """The next envelope the app sent, or `Closed` if it closed instead."""
        message = await asyncio.wait_for(self._from_app.get(), timeout)
        if message["type"] == "websocket.close":
            raise Closed(message.get("code", 1000))
        found: dict[str, Any] = json.loads(message["text"])
        return found

    async def closed(self, timeout: float = TIMEOUT_S) -> int:
        """The code the app closes with, failing if it sends anything first."""
        message = await asyncio.wait_for(self._from_app.get(), timeout)
        assert message["type"] == "websocket.close", message
        code: int = message.get("code", 1000)
        return code

    async def nothing(self, wait: float = 0.2) -> None:
        """Assert the app sends nothing within `wait` seconds."""
        try:
            message = await asyncio.wait_for(self._from_app.get(), wait)
        except TimeoutError:
            return
        raise AssertionError(f"expected nothing, got {message}")


@asynccontextmanager
async def connect(
    app: FastAPI, path: str, *, origin: str | None
) -> AsyncIterator[TestSocket]:
    url = urlsplit(path)
    headers = [] if origin is None else [(b"origin", origin.encode())]
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "scheme": "ws",
        "http_version": "1.1",
        "path": url.path,
        "raw_path": url.path.encode(),
        "query_string": url.query.encode(),
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
        "subprotocols": [],
        "state": {},
    }
    to_app: asyncio.Queue[MutableMapping[str, Any]] = asyncio.Queue()
    from_app: asyncio.Queue[MutableMapping[str, Any]] = asyncio.Queue()
    await to_app.put({"type": "websocket.connect"})
    task = asyncio.create_task(app(scope, to_app.get, from_app.put))
    try:
        first = await asyncio.wait_for(from_app.get(), TIMEOUT_S)
        if first["type"] == "websocket.close":
            raise Refused(first.get("code", 1000))
        assert first["type"] == "websocket.accept", first
        yield TestSocket(to_app, from_app)
    finally:
        await to_app.put({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(task, TIMEOUT_S)
        except TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
