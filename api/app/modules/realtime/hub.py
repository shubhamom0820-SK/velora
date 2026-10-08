"""The sockets one API instance holds, and its one Redis subscription (T-7.4).

02-ARCHITECTURE §6: every instance subscribes for the users connected to it.
One `PubSub` per instance, never one per socket: a user's first socket here
subscribes `user:{id}`, their last one leaving unsubscribes. A reader task
hands each message to every socket of that user, through a bounded queue per
socket, so a slow client never holds the others up: one whose queue is full
is closed (1013, try again later) and reconnects, and the web refetches what
it missed (T-7.12).

`socket.close` (`core/events.py`) is the server's own: it closes every socket
of that user and is never sent to a client.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core import events

log = structlog.get_logger(__name__)

# Messages one socket may have waiting before it counts as too slow.
QUEUE_MAX: Final = 100
# How long the reader waits on Redis before looking again.
READ_TIMEOUT_S: Final = 1.0

# Close codes (RFC 6455's private range for ours).
CLOSE_SIGNED_OUT: Final = 4000
CLOSE_TOO_SLOW: Final = 1013


class Socket:
    """One connection's outbox. The gateway sends what is queued, in order;
    `closing` is the code the hub asked to close with, once it has."""

    def __init__(self) -> None:
        self.outbox: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX)
        self.closing: int | None = None
        self.closed = asyncio.Event()

    def offer(self, text: str) -> None:
        if self.closing is not None:
            return
        try:
            self.outbox.put_nowait(text)
        except asyncio.QueueFull:
            self.close(CLOSE_TOO_SLOW)

    def close(self, code: int) -> None:
        if self.closing is None:
            self.closing = code
            self.closed.set()


class Hub:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._sockets: dict[UUID, set[Socket]] = {}
        self._pubsub: PubSub | None = None
        self._reader: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def count(self, user_id: UUID | None = None) -> int:
        """Sockets held here: one user's, or everyone's."""
        if user_id is not None:
            return len(self._sockets.get(user_id, ()))
        return sum(len(each) for each in self._sockets.values())

    async def join(self, user_id: UUID, socket: Socket) -> None:
        async with self._lock:
            held = self._sockets.setdefault(user_id, set())
            held.add(socket)
            if len(held) == 1:
                pubsub = self._ensure_reading()
                await pubsub.subscribe(_channel(user_id))

    async def leave(self, user_id: UUID, socket: Socket) -> None:
        async with self._lock:
            held = self._sockets.get(user_id)
            if held is None or socket not in held:
                return
            held.discard(socket)
            if not held:
                del self._sockets[user_id]
                if self._pubsub is not None:
                    await self._pubsub.unsubscribe(_channel(user_id))

    def _ensure_reading(self) -> PubSub:
        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()
        if self._reader is None or self._reader.done():
            self._reader = asyncio.create_task(self._read(self._pubsub))
        return self._pubsub

    async def _read(self, pubsub: PubSub) -> None:
        while True:
            if not pubsub.subscribed:
                await asyncio.sleep(0.05)
                continue
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=READ_TIMEOUT_S
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 — the reader must outlive one bad read
                log.warning("realtime.read_failed", error=type(error).__name__)
                await asyncio.sleep(READ_TIMEOUT_S)
                continue
            if message is None or message.get("type") != "message":
                continue
            self.deliver(_user_of(message["channel"]), _text(message["data"]))

    def deliver(self, user_id: UUID | None, text: str) -> None:
        """Hand one envelope to every socket `user_id` has here."""
        if user_id is None:
            return
        held = list(self._sockets.get(user_id, ()))
        if _type_of(text) == events.CLOSE_SOCKETS:
            for socket in held:
                socket.close(CLOSE_SIGNED_OUT)
            return
        for socket in held:
            socket.offer(text)

    async def aclose(self) -> None:
        """Stop reading and let Redis go. Safe to call more than once."""
        if self._reader is not None:
            self._reader.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._reader
            self._reader = None
        if self._pubsub is not None:
            with suppress(Exception):
                await self._pubsub.aclose()  # type: ignore[no-untyped-call]
            self._pubsub = None
        for held in self._sockets.values():
            for socket in held:
                socket.close(CLOSE_SIGNED_OUT)
        self._sockets.clear()


def _channel(user_id: UUID) -> str:
    return f"user:{user_id}"


def _text(data: bytes | str) -> str:
    return data.decode() if isinstance(data, bytes) else data


def _user_of(channel: bytes | str) -> UUID | None:
    name = _text(channel)
    prefix, _, raw = name.partition(":")
    if prefix != "user":
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def _type_of(text: str) -> str | None:
    try:
        found = json.loads(text).get("type")
    except (ValueError, AttributeError):
        return None
    return found if isinstance(found, str) else None
