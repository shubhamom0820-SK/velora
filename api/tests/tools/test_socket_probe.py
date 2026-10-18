"""P-49's socket probe, against the app served for real on a local port: a real
ticket opens the socket and gets its pong; a bad ticket or another site's Origin
is refused at the handshake; the ticket is never printed; and it runs only where
ENV is local or staging (app/tools/socket_probe.py)."""

from __future__ import annotations

import argparse
import asyncio
import io
import uuid
from collections.abc import AsyncIterator

import pytest
import uvicorn
from fastapi import FastAPI

from app.core import config
from app.modules.realtime import service
from app.tools import socket_probe
from tests.conftest import MakeUser

ORIGIN = "http://127.0.0.1:3000"  # make_test_settings' CORS_ORIGINS


@pytest.fixture
async def served(app: FastAPI) -> AsyncIterator[str]:
    """The test app on a free port, over real sockets; its ws:// base."""
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
        )
    )
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started, "the test server didn't start"
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"ws://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


async def test_a_real_ticket_opens_the_socket_and_gets_its_pong(
    app: FastAPI, served: str, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    ticket = await service.issue(app.state.redis, user.id)
    out = io.StringIO()

    code = await socket_probe.probe(served, ticket=ticket, origin=ORIGIN, out=out)

    text = out.getvalue()
    assert code == 0, text
    lines = text.splitlines()
    assert lines[0].startswith("socket opened in ") and lines[0].endswith(" ms")
    assert lines[-1].startswith("pong in ") and lines[-1].endswith(" ms")
    assert ticket not in text


async def test_a_bad_ticket_is_refused_at_the_handshake_and_not_printed(
    served: str,
) -> None:
    out = io.StringIO()
    forged = "not-a-ticket-" + uuid.uuid4().hex

    code = await socket_probe.probe(served, ticket=forged, origin=ORIGIN, out=out)

    assert code == 1
    assert out.getvalue() == "refused at the handshake: HTTP 403\n"


async def test_another_sites_origin_is_refused(
    app: FastAPI, served: str, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    ticket = await service.issue(app.state.redis, user.id)
    out = io.StringIO()

    code = await socket_probe.probe(
        served, ticket=ticket, origin="https://elsewhere.example", out=out
    )

    assert code == 1
    assert out.getvalue() == "refused at the handshake: HTTP 403\n"


async def test_nothing_listening_is_named_without_a_host() -> None:
    out = io.StringIO()

    code = await socket_probe.probe(
        "ws://127.0.0.1:1", ticket="t", origin=ORIGIN, out=out
    )

    assert code == 1
    assert out.getvalue().startswith("failed: ")
    assert "127.0.0.1" not in out.getvalue()


@pytest.mark.parametrize("env", ["production", "env-nobody-has-named-2031"])
async def test_it_refuses_outside_local_and_staging(
    env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An allowlist (rule 16): a name nobody listed is refused like production."""
    settings = config.get_settings().model_copy(update={"ENV": env})
    monkeypatch.setattr(socket_probe, "get_settings", lambda: settings)
    out = io.StringIO()
    args = argparse.Namespace(user=uuid.uuid4(), url="wss://api.example")

    assert await socket_probe.run(args, out) == 2
    assert (
        out.getvalue() == f"socket_probe: refused, ENV={env} (only local and staging)\n"
    )


async def test_a_url_that_isnt_a_socket_is_refused() -> None:
    out = io.StringIO()
    args = argparse.Namespace(user=uuid.uuid4(), url="https://api.example")

    assert await socket_probe.run(args, out) == 2
    assert out.getvalue() == "socket_probe: --url must start with ws:// or wss://\n"
