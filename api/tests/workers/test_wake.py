"""The worker's wake listener (D-261, T-4.5), on this run's Redis: it hears an
id and hands it on, ignores what isn't one, survives a failing handler and a
dropped connection, and backs off so a connection that never holds can't
quietly spend Upstash's commands.

Redis shares pub/sub channels across its databases, so every listener here
uses a channel of its own: another run on this machine publishing a real wake
must not reach these tests, nor theirs reach a real listener."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any, Self
from urllib.parse import urlsplit, urlunsplit

import pytest
from redis.asyncio import Redis

from app.workers import wake
from app.workers.wake import WakeListener
from tests.conftest import CapturedLogs
from tests.infra import TEST_REDIS_URL


def _channel() -> str:
    return f"wake:test:{uuid.uuid4()}"


def _named(name: str) -> Callable[[], Redis]:
    def connect() -> Redis:
        client: Redis = Redis.from_url(TEST_REDIS_URL, client_name=name)
        return client

    return connect


@contextlib.asynccontextmanager
async def _listening(listener: WakeListener) -> AsyncIterator[asyncio.Task[None]]:
    task = asyncio.create_task(listener.run())
    try:
        async with asyncio.timeout(5):
            await listener.subscribed.wait()
        yield task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@contextlib.asynccontextmanager
async def _slow_link(delay_s: float) -> AsyncIterator[str]:
    """A loopback proxy to this run's Redis that holds every byte a client sends
    for `delay_s` before passing it on, as the road to Upstash does: a SUBSCRIBE
    leaves the worker well before the server has it. Yields the proxy's URL."""
    target = urlsplit(TEST_REDIS_URL)
    tasks: set[asyncio.Task[None]] = set()
    writers: list[asyncio.StreamWriter] = []

    async def pipe(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter, delay: float
    ) -> None:
        try:
            while data := await reader.read(65536):
                await asyncio.sleep(delay)
                writer.write(data)
                await writer.drain()
        except OSError:
            pass
        finally:
            writer.close()

    async def serve(
        client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter
    ) -> None:
        server_r, server_w = await asyncio.open_connection(target.hostname, target.port)
        writers.extend((client_w, server_w))
        for task in (
            asyncio.create_task(pipe(client_r, server_w, delay_s)),
            asyncio.create_task(pipe(server_r, client_w, 0)),
        ):
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield urlunsplit(target._replace(netloc=f"127.0.0.1:{port}"))
    finally:
        server.close()
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for writer in writers:
            writer.close()
        await server.wait_closed()


class Heard:
    def __init__(self) -> None:
        self.ids: list[uuid.UUID] = []
        self.event = asyncio.Event()

    async def __call__(self, verification_id: uuid.UUID) -> object:
        self.ids.append(verification_id)
        self.event.set()
        return None

    async def next(self) -> uuid.UUID:
        async with asyncio.timeout(5):
            await self.event.wait()
        self.event.clear()
        return self.ids[-1]


async def test_it_hears_a_wake_and_hands_on_the_id(test_redis: Redis) -> None:
    channel, heard = _channel(), Heard()
    listener = WakeListener(_named("wake-test"), heard, channel=channel)
    verification_id = uuid.uuid4()

    async with _listening(listener):
        assert await test_redis.publish(channel, str(verification_id)) == 1
        assert await heard.next() == verification_id


async def test_subscribed_means_redis_holds_the_subscription(test_redis: Redis) -> None:
    """P-330: `subscribed` waits for Redis to confirm the SUBSCRIBE, not for the
    command to leave, so a wake published the instant it is set is heard, on a
    link slow enough that the command is still on its way. After a reconnect
    too. Before the fix this published to 0 subscribers every time."""
    channel, heard = _channel(), Heard()

    async with _slow_link(0.2) as url:
        for _ in range(3):
            name = f"wake-{uuid.uuid4().hex[:12]}"

            def connect(name: str = name) -> Redis:
                client: Redis = Redis.from_url(url, client_name=name)
                return client

            listener = WakeListener(connect, heard, channel=channel)
            async with _listening(listener):
                verification_id = uuid.uuid4()
                assert await test_redis.publish(channel, str(verification_id)) == 1
                assert await heard.next() == verification_id

                [mine] = [
                    c for c in await test_redis.client_list() if c["name"] == name
                ]
                listener.subscribed.clear()
                assert await test_redis.client_kill_filter(_id=mine["id"]) == 1
                async with asyncio.timeout(10):
                    await listener.subscribed.wait()
                verification_id = uuid.uuid4()
                assert await test_redis.publish(channel, str(verification_id)) == 1
                assert await heard.next() == verification_id


async def test_the_real_channel_is_the_one_the_api_publishes_on() -> None:
    from app.core.queue import VERIFY_SELFIE, wake_channel

    assert wake.CHANNEL == wake_channel(VERIFY_SELFIE) == "wake:verify_selfie"


async def test_what_isnt_an_id_is_ignored_and_it_listens_on(
    test_redis: Redis, captured_logs: CapturedLogs
) -> None:
    channel, heard = _channel(), Heard()
    listener = WakeListener(_named("wake-test"), heard, channel=channel)
    verification_id = uuid.uuid4()

    async with _listening(listener):
        await test_redis.publish(channel, "raw/someone/a-key")
        await test_redis.publish(channel, str(verification_id))
        assert await heard.next() == verification_id

    assert heard.ids == [verification_id]
    assert "wake.not_an_id" in captured_logs.text
    assert "raw/someone/a-key" not in captured_logs.text  # never echoed (rule 15)
    captured_logs.assert_listening()


async def test_a_failing_comparison_never_stops_the_listening(
    test_redis: Redis,
) -> None:
    channel, heard = _channel(), Heard()
    first = uuid.uuid4()

    async def handle(verification_id: uuid.UUID) -> object:
        if verification_id == first:
            raise RuntimeError("the comparison failed: the queued job will run")
        return await heard(verification_id)

    listener = WakeListener(_named("wake-test"), handle, channel=channel)
    second = uuid.uuid4()

    async with _listening(listener):
        await test_redis.publish(channel, str(first))
        await test_redis.publish(channel, str(second))
        assert await heard.next() == second


async def test_a_dropped_connection_is_made_again(
    test_redis: Redis, captured_logs: CapturedLogs
) -> None:
    """The connection is killed from the server's side, as a Redis restart
    or Upstash's proxy would: it subscribes again, and hears the next wake.
    The drop is the listener's to see and log, never redis-py's to hide."""
    channel, heard, name = _channel(), Heard(), f"wake-{uuid.uuid4().hex[:12]}"
    listener = WakeListener(_named(name), heard, channel=channel)

    async with _listening(listener):
        [mine] = [c for c in await test_redis.client_list() if c["name"] == name]
        listener.subscribed.clear()
        assert await test_redis.client_kill_filter(_id=mine["id"]) == 1
        async with asyncio.timeout(10):
            await listener.subscribed.wait()
        verification_id = uuid.uuid4()
        await test_redis.publish(channel, str(verification_id))
        assert await heard.next() == verification_id

    [dropped] = [e for e in captured_logs.events if e["event"] == "wake.disconnected"]
    assert (dropped["log_level"], dropped["retry_in_s"]) == ("warning", 1.0)


class Refusing:
    """A Redis that can't be reached: every connection fails at subscribe."""

    def pubsub(self) -> Self:
        return self

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def subscribe(self, *channels: str) -> None:
        raise ConnectionError("unreachable")

    async def aclose(self) -> None:
        return None


class HoldsThenDrops(Refusing):
    """Subscribes, Redis confirming it, holds while the clock moves on by
    `held`, then drops."""

    def __init__(self, clock: ModuleType, held: timedelta) -> None:
        self.clock, self.held = clock, held
        self.confirmed = False

    async def subscribe(self, *channels: str) -> None:
        return None

    async def get_message(self, **kwargs: Any) -> dict[str, object]:
        if not self.confirmed:
            self.confirmed = True
            return {"type": "subscribe", "channel": b"wake", "data": 1}
        self.clock.advance(self.held)
        raise ConnectionError("dropped")


async def _waits(connect: Callable[[], Any], tries: int) -> list[float]:
    """The waits between connections, until `tries` of them."""
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == tries:
            raise asyncio.CancelledError

    listener = WakeListener(connect, Heard(), channel=_channel(), sleep=sleep)
    with pytest.raises(asyncio.CancelledError):
        await listener.run()
    return waits


async def test_a_connection_that_never_holds_backs_off_to_once_in_5_minutes() -> None:
    """At most one SUBSCRIBE every 300 seconds, whatever Upstash does: 8,640 a
    month, under 2% of Free's 500,000 (D-091's budget)."""
    waits = await _waits(Refusing, 12)

    assert waits == [1, 2, 4, 8, 16, 32, 64, 128, 256, 300, 300, 300]
    assert 30 * 24 * 3600 / wake.MAX_BACKOFF_S == 8640


@pytest.mark.parametrize(
    ("held", "waits"),
    [
        (timedelta(seconds=299), [1, 2, 4, 8]),
        (timedelta(seconds=300), [1, 1, 1, 1]),
    ],
    ids=["dropping-early-keeps-backing-off", "held-5-minutes-starts-again"],
)
async def test_it_starts_again_from_a_second_only_after_a_connection_held(
    clock: ModuleType,
    held: timedelta,
    waits: list[float],
) -> None:
    clock.freeze(datetime(2026, 10, 5, 12, 0, tzinfo=UTC))

    assert await _waits(lambda: HoldsThenDrops(clock, held), 4) == waits
