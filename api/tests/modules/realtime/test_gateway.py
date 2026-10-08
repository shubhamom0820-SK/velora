"""`/ws` (T-7.4; 02-ARCHITECTURE §6): a ticket opens one socket from the web's
own origin; every event published to `user:{id}` reaches that user's sockets
and nobody else's; `ping` is answered; silence closes it; a revoked session's
`socket.close` closes them all; the hub lets Redis go of a user with none left.

The app runs in process (`tests/ws.py`), sharing the test's `db` and Redis as
`client` does, so a request's events reach these sockets as in the app (P-64).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis

from app.core import events
from app.core.enums import Gender
from app.main import close_resources
from app.modules.realtime import hub as hub_module
from app.modules.realtime import service
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer
from tests.ws import Closed, Refused, connect

pytestmark = pytest.mark.usefixtures("db")

ORIGIN = "http://127.0.0.1:3000"  # make_test_settings' CORS_ORIGINS


async def _path(redis: Redis, user_id: uuid.UUID) -> str:
    return f"/ws?ticket={await service.issue(redis, user_id)}"


async def _publish(redis: Redis, user_id: uuid.UUID, type_: str, **data: Any) -> None:
    await events.publish([events.Event(user_id, type_, data)], redis)


async def _subscribed(redis: Redis, user_id: uuid.UUID, count: int = 1) -> None:
    """Wait until the hub holds `user:{id}` on Redis (or has let it go, at 0)."""
    channel = f"user:{user_id}"
    for _ in range(100):
        found = dict(await redis.pubsub_numsub(channel))
        if found.get(channel.encode(), 0) == count:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"{channel} never had {count} subscriber(s)")


async def test_an_event_reaches_every_socket_of_its_user_and_nobody_else(
    app: FastAPI, test_redis: Redis
) -> None:
    me, other = uuid.uuid4(), uuid.uuid4()
    async with (
        connect(app, await _path(test_redis, me), origin=ORIGIN) as phone,
        connect(app, await _path(test_redis, me), origin=ORIGIN) as laptop,
        connect(app, await _path(test_redis, other), origin=ORIGIN) as theirs,
    ):
        await _subscribed(test_redis, me)
        await _publish(test_redis, me, "message.new", thread_id="t")

        for socket in (phone, laptop):
            envelope = await socket.receive()
            assert (envelope["type"], envelope["data"]) == (
                "message.new",
                {"thread_id": "t"},
            )
            uuid.UUID(envelope["id"])
        await theirs.nothing()


async def test_a_requests_event_reaches_the_socket(
    app: FastAPI,
    client: AsyncClient,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """End to end: a message sent by REST arrives on the other person's socket."""
    man, _ = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id
    man_id = man.id

    async with connect(app, await _path(test_redis, man_id), origin=ORIGIN) as his:
        await _subscribed(test_redis, man_id)
        sent = await client.post(
            f"/v1/threads/{thread_id}/messages",
            json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hi"},
            headers=bearer(her_token),
        )
        envelope = await his.receive()

    assert sent.status_code == 200
    assert envelope["type"] == "message.new"
    assert envelope["data"]["message"]["body"] == "Hi"
    assert envelope["data"]["message"]["mine"] is False


async def test_a_ticket_opens_one_socket_once(app: FastAPI, test_redis: Redis) -> None:
    path = await _path(test_redis, uuid.uuid4())
    async with connect(app, path, origin=ORIGIN):
        pass

    with pytest.raises(Refused) as again:
        async with connect(app, path, origin=ORIGIN):
            pass

    assert again.value.code == service.CLOSE_NO_TICKET


@pytest.mark.parametrize("path", ["/ws", "/ws?ticket=", "/ws?ticket=nope"])
async def test_no_ticket_no_socket(app: FastAPI, path: str) -> None:
    with pytest.raises(Refused) as refused:
        async with connect(app, path, origin=ORIGIN):
            pass

    assert refused.value.code == service.CLOSE_NO_TICKET


@pytest.mark.parametrize(
    "origin", [None, "https://evil.example", "http://localhost:3000", "null"]
)
async def test_only_the_webs_own_origin_opens_one(
    app: FastAPI, test_redis: Redis, origin: str | None
) -> None:
    user_id = uuid.uuid4()
    path = await _path(test_redis, user_id)

    with pytest.raises(Refused) as refused:
        async with connect(app, path, origin=origin):
            pass

    assert refused.value.code == service.CLOSE_FORBIDDEN
    # Refused before the ticket was read: it still opens one from the web.
    async with connect(app, path, origin=ORIGIN):
        pass


async def test_ping_is_answered_pong(app: FastAPI, test_redis: Redis) -> None:
    async with connect(app, await _path(test_redis, uuid.uuid4()), origin=ORIGIN) as ws:
        await ws.send({"type": "ping", "id": str(uuid.uuid4()), "data": {}})
        envelope = await ws.receive()
        await ws.send({"type": "typing", "data": {}})  # T-7.5's: ignored here
        await ws.nothing()

    assert (envelope["type"], envelope["data"]) == ("pong", {})


async def test_a_silent_socket_is_closed(
    app: FastAPI, test_redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "IDLE_S", 0.2)
    async with connect(app, await _path(test_redis, uuid.uuid4()), origin=ORIGIN) as ws:
        assert await ws.closed() == service.CLOSE_IDLE


async def test_socket_close_closes_every_socket_of_that_user_alone(
    app: FastAPI, test_redis: Redis
) -> None:
    me, other = uuid.uuid4(), uuid.uuid4()
    async with (
        connect(app, await _path(test_redis, me), origin=ORIGIN) as phone,
        connect(app, await _path(test_redis, me), origin=ORIGIN) as laptop,
        connect(app, await _path(test_redis, other), origin=ORIGIN) as theirs,
    ):
        await _subscribed(test_redis, me)
        await _subscribed(test_redis, other)
        await _publish(test_redis, me, events.CLOSE_SOCKETS)

        assert await phone.closed() == hub_module.CLOSE_SIGNED_OUT
        assert await laptop.closed() == hub_module.CLOSE_SIGNED_OUT
        await _publish(test_redis, other, "still.here")
        assert (await theirs.receive())["type"] == "still.here"


async def test_deleting_the_account_closes_its_sockets(
    app: FastAPI, client: AsyncClient, test_redis: Redis, make_user: MakeUser
) -> None:
    """Every session revoked (T-9.6) queues `socket.close`, published when
    the request ends."""
    user, token = await make_user()
    user_id = user.id

    async with connect(app, await _path(test_redis, user_id), origin=ORIGIN) as ws:
        await _subscribed(test_redis, user_id)
        response = await client.delete("/v1/me", headers=bearer(token))
        code = await ws.closed()

    assert response.status_code == 202
    assert code == hub_module.CLOSE_SIGNED_OUT


async def test_the_last_socket_gone_the_hub_lets_redis_go(
    app: FastAPI, test_redis: Redis
) -> None:
    me = uuid.uuid4()
    async with connect(app, await _path(test_redis, me), origin=ORIGIN):
        async with connect(app, await _path(test_redis, me), origin=ORIGIN):
            await _subscribed(test_redis, me)
            assert service.hub_of(app).count(me) == 2
        await _subscribed(test_redis, me)
        assert service.hub_of(app).count(me) == 1

    await _subscribed(test_redis, me, count=0)
    assert service.hub_of(app).count(me) == 0


def test_a_slow_socket_is_closed_never_waited_for() -> None:
    """A full outbox closes the socket (1013) rather than holding the hub."""
    socket = hub_module.Socket()
    for n in range(hub_module.QUEUE_MAX):
        socket.offer(f"{n}")
    assert socket.closing is None

    socket.offer("one too many")

    assert socket.closing == hub_module.CLOSE_TOO_SLOW
    assert socket.outbox.qsize() == hub_module.QUEUE_MAX


def test_the_hub_never_forwards_its_own_close() -> None:
    hub = hub_module.Hub(redis=None)  # type: ignore[arg-type]
    socket = hub_module.Socket()
    user_id = uuid.uuid4()
    hub._sockets[user_id] = {socket}

    hub.deliver(user_id, events.Event(user_id, events.CLOSE_SOCKETS, {}).envelope())

    assert socket.outbox.empty()
    assert socket.closing == hub_module.CLOSE_SIGNED_OUT


async def test_a_closed_socket_raises_on_receive(
    app: FastAPI, test_redis: Redis
) -> None:
    me = uuid.uuid4()
    async with connect(app, await _path(test_redis, me), origin=ORIGIN) as ws:
        await _subscribed(test_redis, me)
        await _publish(test_redis, me, events.CLOSE_SOCKETS)
        with pytest.raises(Closed):
            await ws.receive()


async def test_shutting_down_closes_every_socket(
    app: FastAPI, test_redis: Redis
) -> None:
    """The lifespan's `close_resources` lets the hub go: sockets close, and
    Redis is let go of, before the app's own Redis client is."""
    me = uuid.uuid4()
    async with connect(app, await _path(test_redis, me), origin=ORIGIN) as ws:
        await _subscribed(test_redis, me)
        await close_resources(app)
        assert await ws.closed() == hub_module.CLOSE_SIGNED_OUT
    await _subscribed(test_redis, me, count=0)
