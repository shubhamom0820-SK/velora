"""The socket side of real time (T-7.4; 02-ARCHITECTURE §6, D-557).

**Tickets.** `POST /v1/ws/ticket` gives a signed-in, onboarded user a ticket:
32 random bytes, kept in Redis for 30 seconds by its SHA-256 only, naming the
user, and taken (`GETDEL`) the moment a socket presents it, so it opens one
socket, once. The access token never travels in a URL, where logs keep it.

**The socket** (`/ws?ticket=`): from one of the exact web origins (CORS's own
list) or refused before it opens; with a ticket or closed (4401). Then it is
the hub's: every event published to `user:{id}` reaches it, in §6's envelope.
The client's `ping` is answered `pong`; a socket silent for `IDLE_S` is closed
(4408). Sending is never the socket's: messages go by REST (§6).

**Closing.** Where a user's sessions are revoked (sign-out, a refresh replayed,
five wrong PINs, a deleted account) the service queues `socket.close` in the
same transaction, and every socket of theirs closes (4000). A freeze or a ban
does the same once a task writes one (T-9.2, T-9.5). Nothing here reads the
database: a socket holds no connection.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import uuid
from contextlib import suppress
from typing import Final
from uuid import UUID

from fastapi import FastAPI, WebSocket
from redis.asyncio import Redis
from starlette.websockets import WebSocketState

from app.modules.realtime.hub import Hub, Socket

TICKET_PREFIX: Final = "ws:ticket:"
TICKET_TTL_S: Final = 30
# Longer than any ticket this API writes; anything longer is no ticket.
TICKET_MAX: Final = 100
# The client pings well inside this; a socket silent this long is gone.
IDLE_S: Final = 60.0

CLOSE_NO_TICKET: Final = 4401
CLOSE_FORBIDDEN: Final = 4403
CLOSE_IDLE: Final = 4408

PING: Final = "ping"
PONG: Final = "pong"


def _key(ticket: str) -> str:
    return TICKET_PREFIX + hashlib.sha256(ticket.encode()).hexdigest()


async def issue(redis: Redis, user_id: UUID) -> str:
    """A ticket for one socket of `user_id`'s, good for `TICKET_TTL_S`."""
    ticket = secrets.token_urlsafe(32)
    await redis.set(_key(ticket), str(user_id), ex=TICKET_TTL_S)
    return ticket


async def redeem(redis: Redis, ticket: str | None) -> UUID | None:
    """The user a ticket names, taking it so it never opens a second socket;
    None for no ticket, a spent or expired one, or one we never wrote."""
    if not ticket or len(ticket) > TICKET_MAX:
        return None
    raw = await redis.getdel(_key(ticket))
    if raw is None:
        return None
    try:
        return UUID(raw.decode() if isinstance(raw, bytes) else raw)
    except ValueError:
        return None


def hub_of(app: FastAPI) -> Hub:
    """This instance's hub, made with its first socket."""
    hub: Hub | None = getattr(app.state, "hub", None)
    if hub is None:
        hub = Hub(app.state.redis)
        app.state.hub = hub
    return hub


async def serve(websocket: WebSocket) -> None:
    """One socket, from the handshake to its close."""
    app: FastAPI = websocket.app
    if websocket.headers.get("origin") not in app.state.settings.CORS_ORIGINS:
        await websocket.close(code=CLOSE_FORBIDDEN)
        return
    user_id = await redeem(app.state.redis, websocket.query_params.get("ticket"))
    if user_id is None:
        await websocket.close(code=CLOSE_NO_TICKET)
        return
    await websocket.accept()
    socket = Socket()
    hub = hub_of(app)
    await hub.join(user_id, socket)
    try:
        await _run(websocket, socket)
    finally:
        await hub.leave(user_id, socket)


async def _run(websocket: WebSocket, socket: Socket) -> None:
    tasks = {
        asyncio.create_task(_send_all(websocket, socket)),
        asyncio.create_task(_receive_all(websocket, socket)),
        asyncio.create_task(socket.closed.wait()),
    }
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if socket.closing is not None and websocket.application_state is (
        WebSocketState.CONNECTED
    ):
        with suppress(Exception):
            await websocket.close(code=socket.closing)


async def _send_all(websocket: WebSocket, socket: Socket) -> None:
    while True:
        await websocket.send_text(await socket.outbox.get())


async def _receive_all(websocket: WebSocket, socket: Socket) -> None:
    """Until the client goes: `ping` answered, anything else ignored (T-7.5
    relays `typing`), silence past `IDLE_S` closing the socket."""
    while True:
        try:
            message = await asyncio.wait_for(websocket.receive(), timeout=IDLE_S)
        except TimeoutError:
            socket.close(CLOSE_IDLE)
            return
        if message["type"] == "websocket.disconnect":
            return
        if _type_of(message.get("text")) == PING:
            socket.offer(
                json.dumps({"type": PONG, "id": str(uuid.uuid4()), "data": {}})
            )


def _type_of(text: str | None) -> str | None:
    if not text:
        return None
    try:
        found = json.loads(text).get("type")
    except (ValueError, AttributeError):
        return None
    return found if isinstance(found, str) else None
