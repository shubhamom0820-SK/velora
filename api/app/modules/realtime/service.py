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

**Typing** (T-7.5, D-670). The client's `typing` names a Thread; the other
person hears it, never the typist. At most one a Thread every
`TYPING_EVERY_S` and `TYPING_PER_MINUTE` in all, both in Redis and both
before the database is read: then one short session asks whether they are
one of its two with no block between them. Anything else is dropped quietly,
and the socket stays open: §6 has no error to send.

**Closing.** Where a user's sessions are revoked (sign-out, a refresh replayed,
five wrong PINs, a deleted account) the service queues `socket.close` in the
same transaction, and every socket of theirs closes (4000). A freeze or a ban
does the same once a task writes one (T-9.2, T-9.5). Only a relayed `typing`
reads the database, in a session of its own that closes at once: a socket
holds no connection.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import uuid
from contextlib import suppress
from typing import Any, Final
from uuid import UUID

import structlog
from fastapi import FastAPI, WebSocket
from redis.asyncio import Redis
from starlette.websockets import WebSocketState

from app.core import events, ratelimit
from app.core.db import SessionOpener
from app.modules.messages import service as messages_service
from app.modules.realtime.hub import Hub, Socket

log = structlog.get_logger(__name__)

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
TYPING: Final = "typing"

# §6's throttle, one a Thread every 3 seconds; and a ceiling across Threads,
# so a client naming Thread after Thread can't make typing a stream of reads
# (D-670).
TYPING_EVERY_S: Final = 3
TYPING_PER_MINUTE: Final = 40
# A relay waits no longer than an event's publish (`core/events.py`).
TYPING_TIMEOUT_S: Final = 1.0


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


async def serve(websocket: WebSocket, open_session: SessionOpener) -> None:
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
        await _run(websocket, socket, _Typist(app.state.redis, open_session, user_id))
    finally:
        await hub.leave(user_id, socket)


async def _run(websocket: WebSocket, socket: Socket, typist: _Typist) -> None:
    tasks = {
        asyncio.create_task(_send_all(websocket, socket)),
        asyncio.create_task(_receive_all(websocket, socket, typist)),
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


async def _receive_all(websocket: WebSocket, socket: Socket, typist: _Typist) -> None:
    """Until the client goes: `ping` answered, `typing` relayed, anything else
    ignored, silence past `IDLE_S` closing the socket."""
    while True:
        try:
            message = await asyncio.wait_for(websocket.receive(), timeout=IDLE_S)
        except TimeoutError:
            socket.close(CLOSE_IDLE)
            return
        if message["type"] == "websocket.disconnect":
            return
        envelope = _envelope(message.get("text"))
        if envelope is None:
            continue
        type_, data = envelope
        if type_ == PING:
            socket.offer(
                json.dumps({"type": PONG, "id": str(uuid.uuid4()), "data": {}})
            )
        elif type_ == TYPING:
            await typist.relay(data)


class _Typist:
    """One socket's user, typing (T-7.5, D-670)."""

    def __init__(
        self, redis: Redis, open_session: SessionOpener, user_id: UUID
    ) -> None:
        self._redis = redis
        self._open_session = open_session
        self._user_id = user_id

    async def relay(self, data: dict[str, Any]) -> None:
        """`typing` in the Thread `data` names, to its other person; a failure
        is logged and the socket goes on."""
        thread_id = _uuid(data.get("thread_id"))
        if thread_id is None:
            return
        try:
            async with asyncio.timeout(TYPING_TIMEOUT_S):
                await self._relay(thread_id)
        except Exception as error:  # noqa: BLE001 — a lost typing never ends a socket
            log.warning("realtime.typing_failed", error=type(error).__name__)

    async def _relay(self, thread_id: UUID) -> None:
        user = str(self._user_id)
        throttle = await ratelimit.hit(
            self._redis,
            "ws_typing_thread",
            f"{user}:{thread_id}",
            limit=1,
            window_s=TYPING_EVERY_S,
        )
        if not throttle.allowed:
            return
        ceiling = await ratelimit.hit(
            self._redis, "ws_typing", user, limit=TYPING_PER_MINUTE, window_s=60
        )
        if not ceiling.allowed:
            return
        async with self._open_session() as session:
            other = await messages_service.typing_recipient(
                session, self._user_id, thread_id
            )
        if other is None:
            return
        await events.publish(
            [events.Event(other, TYPING, {"thread_id": str(thread_id)})], self._redis
        )


def _envelope(text: str | None) -> tuple[str, dict[str, Any]] | None:
    """`(type, data)` from a client's envelope; None if it isn't one."""
    if not text:
        return None
    try:
        found = json.loads(text)
    except ValueError:
        return None
    if not isinstance(found, dict) or not isinstance(found.get("type"), str):
        return None
    data = found.get("data")
    return found["type"], data if isinstance(data, dict) else {}


def _uuid(raw: object) -> UUID | None:
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None
