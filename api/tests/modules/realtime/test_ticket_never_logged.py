"""A socket's ticket never reaches a log line (rule 15; T-9.13, P-780).

Uvicorn writes a socket's path with its query on `uvicorn.error`
(`"WebSocket /ws?ticket=…" [accepted]`) and an HTTP request's on
`uvicorn.access`. Served for real on a local port, through uvicorn's own
protocol code, as the Dockerfile serves it: the lines are written, and neither
carries its query."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.typing import Origin

from app.modules.realtime import service
from tests.conftest import MakeUser

ORIGIN = Origin("http://127.0.0.1:3000")  # make_test_settings' CORS_ORIGINS
REQUEST_LINES = ("uvicorn.access", "uvicorn.error")


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
async def served(app: FastAPI) -> AsyncIterator[tuple[int, _Lines]]:
    """The app on a free port with uvicorn's request lines on, as deployed;
    every line uvicorn writes on its two request loggers, as formatted."""
    config = uvicorn.Config(
        app, host="127.0.0.1", port=0, lifespan="off", log_level="info"
    )  # Its dictConfig runs here, after create_app configured our logging.
    lines = _Lines()
    for name in REQUEST_LINES:
        logging.getLogger(name).addHandler(lines)
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started, "the test server didn't start"
        yield server.servers[0].sockets[0].getsockname()[1], lines
    finally:
        server.should_exit = True
        await task
        for name in REQUEST_LINES:
            logging.getLogger(name).removeHandler(lines)


async def test_a_sockets_ticket_is_never_in_its_line(
    app: FastAPI, served: tuple[int, _Lines], make_user: MakeUser
) -> None:
    port, lines = served
    user, _ = await make_user()
    ticket = await service.issue(app.state.redis, user.id)

    async with connect(
        f"ws://127.0.0.1:{port}/ws?ticket={ticket}", origin=ORIGIN
    ) as socket:
        await socket.ping()
    # A ticket refused, already spent: its line names the path too.
    with pytest.raises((InvalidStatus, ConnectionClosed)):
        async with connect(
            f"ws://127.0.0.1:{port}/ws?ticket={ticket}", origin=ORIGIN
        ) as socket:
            await socket.recv()

    sockets = [line for line in lines.lines if '"WebSocket /ws' in line]
    assert len(sockets) >= 2, lines.lines
    assert [line for line in lines.lines if ticket in line] == []
    assert [line for line in sockets if "?" in line] == []


async def test_an_http_requests_query_is_never_in_its_line(
    served: tuple[int, _Lines],
) -> None:
    port, lines = served
    marker = "q-9b1f0c7e-never-logged"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://127.0.0.1:{port}/healthz", params={"ticket": marker}
        )
    assert response.status_code == 200

    requests = [line for line in lines.lines if '"GET /healthz' in line]
    assert len(requests) == 1, lines.lines
    assert [line for line in lines.lines if marker in line] == []
    assert "?" not in requests[0]
