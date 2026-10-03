"""Count network round trips to Postgres, deterministically (P-53, for P-50).

A TCP proxy in front of the test database. Each time the client sends after the
server has answered, or first, is one round trip: the client waits for a reply
before it speaks again. How the bytes happen to be split into packets doesn't
change the count, so it holds in CI as it does locally.

Use: `async with RoundTrips() as trips:` gives `trips.url` for an engine and
`trips.count`, which `trips.reset()` zeroes.
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Self

from sqlalchemy.engine import make_url

from tests.infra import TEST_DATABASE_URL


class RoundTrips:
    def __init__(self, target_url: str = TEST_DATABASE_URL) -> None:
        target = make_url(target_url)
        self._target = (target.host or "127.0.0.1", target.port or 5432)
        self._target_url = target
        self.count = 0
        self._server: asyncio.Server | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def url(self) -> str:
        """The test database's URL, through the proxy."""
        assert self._server is not None, "use RoundTrips as `async with`"
        port = self._server.sockets[0].getsockname()[1]
        return self._target_url.set(host="127.0.0.1", port=port).render_as_string(
            hide_password=False
        )

    def reset(self) -> None:
        self.count = 0

    async def __aenter__(self) -> Self:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._server is not None
        self._server.close()
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._server.wait_closed()

    async def _handle(
        self, client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter
    ) -> None:
        server_r, server_w = await asyncio.open_connection(*self._target)
        # Who spoke last on this connection: a client send after the server's
        # answer (or as the opening move) starts a new round trip.
        last = {"speaker": "server"}

        async def pipe(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter, speaker: str
        ) -> None:
            try:
                while data := await reader.read(65536):
                    if speaker == "client" and last["speaker"] == "server":
                        self.count += 1
                    last["speaker"] = speaker
                    writer.write(data)
                    await writer.drain()
            except (ConnectionError, asyncio.CancelledError):
                pass
            finally:
                writer.close()

        for coro in (
            pipe(client_r, server_w, "client"),
            pipe(server_r, client_w, "server"),
        ):
            task = asyncio.ensure_future(coro)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
