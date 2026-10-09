"""The worker's ear for wakes (D-261, T-4.5): a selfie decided in seconds, not
at the worker's next look at the queue.

ARQ looks at the queue every 10 seconds (D-091), because each look is a
command Upstash's Free plan counts. A woman at the selfie step waits on her
result, so `verification.service.submit` also publishes the verification's id
on `wake:verify_selfie` once its transaction commits, and this listener,
subscribed on a connection of its own, runs the comparison as soon as it hears
it, one at a time.

It only makes the job sooner. The queued `verify_selfie` job is still the one
sure to run: a wake missed while this was reconnecting, or while the worker
restarted, costs the person those 10 seconds and nothing else. Both may run
the same comparison; the decision is written once, under the user's lock
(`verification.service._record`).

**What it costs Upstash:** nothing while idle. Subscribed, the connection is
kept alive by PING every `HEALTH_CHECK_S`, which Upstash doesn't charge
(D-091's quote). Each wake is one PUBLISH, plus the delivery if Upstash counts
it (its pages don't say: measured on staging). Each reconnect is one SUBSCRIBE;
they back off to one every `MAX_BACKOFF_S`, and start again from a second only
after a connection held that long, so even one that never holds costs at most
8,640 a month. A drop is logged at warning level, so a connection that keeps
dropping is seen, not quietly paid for. TCP keepalive notices a connection
that died without a word in about a minute and a half.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core import clock
from app.core.queue import VERIFY_SELFIE, wake_channel

log = structlog.get_logger(__name__)

CHANNEL: Final = wake_channel(VERIFY_SELFIE)
HEALTH_CHECK_S: Final = 30
FIRST_BACKOFF_S: Final = 1.0
MAX_BACKOFF_S: Final = 300.0

Handler = Callable[[UUID], Awaitable[object]]


class WakeListener:
    """Subscribes to `CHANNEL` and hands each verification id it hears to
    `handle`, one at a time, until cancelled. A message that isn't an id is
    ignored; a failure in `handle` is logged and never stops the listening."""

    def __init__(
        self,
        connect: Callable[[], Redis],
        handle: Handler,
        *,
        channel: str = CHANNEL,
        id_name: str = "verification_id",
        max_backoff_s: float = MAX_BACKOFF_S,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._connect = connect
        self._handle = handle
        # A test listens on a channel of its own: Redis shares channels across
        # databases, so every run on this machine would hear the real one.
        self._channel = channel
        # What the id heard is, by name, in the logs.
        self._id_name = id_name
        self._max_backoff_s = max_backoff_s
        self._sleep = sleep
        self._since: datetime | None = None
        # Set once Redis confirms the subscription, for tests and for whoever
        # waits on it.
        self.subscribed = asyncio.Event()

    async def run(self) -> None:
        backoff = FIRST_BACKOFF_S
        while True:
            self._since = None
            try:
                await self._listen()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 — reconnect, whatever broke
                self.subscribed.clear()
                held = self._since is not None and (
                    (clock.now() - self._since).total_seconds() >= self._max_backoff_s
                )
                if held:
                    backoff = FIRST_BACKOFF_S
                log.warning(
                    "wake.disconnected",
                    error=type(error).__name__,
                    retry_in_s=backoff,
                )
                await self._sleep(backoff)
                backoff = min(backoff * 2, self._max_backoff_s)

    async def _listen(self) -> None:
        client = self._connect()
        try:
            async with client.pubsub() as pubsub:
                await pubsub.subscribe(self._channel)
                await self._confirmed(pubsub)
                self._since = clock.now()
                self.subscribed.set()
                log.info("wake.listening", channel=self._channel)
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=HEALTH_CHECK_S
                    )
                    if message is not None:
                        await self._heard(message.get("data"))
        finally:
            await client.aclose()

    @staticmethod
    async def _confirmed(pubsub: PubSub) -> None:
        """Until Redis confirms the SUBSCRIBE: `subscribe()` only sends it, and
        a wake published before the server has it finds no one listening
        (P-330). Redis confirms before it delivers anything on the channel."""
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=False, timeout=HEALTH_CHECK_S
            )
            if message is not None and message["type"] == "subscribe":
                return

    async def _heard(self, data: object) -> None:
        try:
            raw = data.decode() if isinstance(data, bytes) else str(data)
            verification_id = UUID(raw)
        except ValueError:
            log.warning("wake.not_an_id")
            return
        log.info("wake.heard", **{self._id_name: str(verification_id)})
        try:
            await self._handle(verification_id)
        except Exception as error:  # noqa: BLE001 — the queued job still runs
            log.info(
                "wake.left_to_the_queue",
                why=type(error).__name__,
                **{self._id_name: str(verification_id)},
            )


# Probe an idle connection after a minute, every 10 seconds, three times: where
# the platform names these options (Linux, where the worker runs).
_KEEPALIVE: Final = {
    option: value
    for name, value in (("TCP_KEEPIDLE", 60), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3))
    if (option := getattr(socket, name, None)) is not None
}


def connect_to(redis_url: str) -> Callable[[], Redis]:
    """A fresh client per connection, its PING keeping it alive while idle."""

    def connect() -> Redis:
        client: Redis = Redis.from_url(
            redis_url,
            health_check_interval=HEALTH_CHECK_S,
            socket_keepalive=True,
            socket_keepalive_options=_KEEPALIVE,
        )
        return client

    return connect
