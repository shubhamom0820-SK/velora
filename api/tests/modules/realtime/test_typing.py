"""`typing` on the socket (T-7.5; 02-ARCHITECTURE §6, D-670): the other person
in the Thread hears it, never the typist; one a Thread every 3 seconds and 40
a minute in all, both before the database is read; nothing across a block or
in a Thread that isn't theirs; anything malformed dropped, the socket open.

The app runs in process (`tests/ws.py`); the relay's short session is the
test's `db`, as a request's is (`session_opener_for_the_app`).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from types import SimpleNamespace as Namespace
from typing import Any

import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.db import session_opener
from app.core.enums import Gender
from app.modules.realtime import service
from app.modules.users.models import User
from tests import ws
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import block
from tests.ws import connect

pytestmark = pytest.mark.usefixtures("db")

ORIGIN = "http://127.0.0.1:3000"  # make_test_settings' CORS_ORIGINS
NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)


async def _path(redis: Redis, user_id: uuid.UUID) -> str:
    return f"/ws?ticket={await service.issue(redis, user_id)}"


async def _subscribed(redis: Redis, user_id: uuid.UUID) -> None:
    channel = f"user:{user_id}"
    for _ in range(100):
        found = dict(await redis.pubsub_numsub(channel))
        if found.get(channel.encode(), 0) == 1:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"{channel} never subscribed")


async def _type(socket: ws.TestSocket, thread_id: Any) -> None:
    await socket.send(
        {
            "type": "typing",
            "id": str(uuid.uuid4()),
            "data": {"thread_id": str(thread_id)},
        }
    )


async def _settled(socket: ws.TestSocket) -> None:
    """Everything sent before this has been handled: the socket answers in
    order, so its `pong` comes after them, and before anything else of its own."""
    await socket.send({"type": "ping", "id": str(uuid.uuid4()), "data": {}})
    assert (await socket.receive())["type"] == "pong"


async def _pair(
    make_user: MakeUser, make_thread: MakeThread
) -> tuple[User, User, uuid.UUID]:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    return man, woman, thread.id


@pytest.mark.parametrize("typist", ["her", "him"])
async def test_the_other_person_hears_it_and_the_typist_doesnt(
    app: FastAPI,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
    typist: str,
) -> None:
    man, woman, thread_id = await _pair(make_user, make_thread)
    me, them = (woman.id, man.id) if typist == "her" else (man.id, woman.id)

    async with (
        connect(app, await _path(test_redis, me), origin=ORIGIN) as mine,
        connect(app, await _path(test_redis, me), origin=ORIGIN) as my_other,
        connect(app, await _path(test_redis, them), origin=ORIGIN) as theirs,
    ):
        await _subscribed(test_redis, me)
        await _subscribed(test_redis, them)
        await _type(mine, thread_id)
        heard = await theirs.receive()
        await _settled(mine)
        await my_other.nothing()

    assert heard["type"] == "typing"
    uuid.UUID(heard["id"])
    # Exactly this: no name, no countdown, no price (D-554).
    assert heard["data"] == {"thread_id": str(thread_id)}


async def test_one_a_thread_every_three_seconds(
    app: FastAPI,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread)
    man_id, woman_id = man.id, woman.id

    async with (
        connect(app, await _path(test_redis, woman_id), origin=ORIGIN) as hers,
        connect(app, await _path(test_redis, man_id), origin=ORIGIN) as his,
    ):
        await _subscribed(test_redis, man_id)
        await _type(hers, thread_id)
        await _type(hers, thread_id)
        # Handled before the clock moves: the socket reads in its own task.
        await _settled(hers)
        clock.freeze(NOON + timedelta(seconds=2))
        await _type(hers, thread_id)
        await _settled(hers)
        first = await his.receive()
        await his.nothing()

        clock.freeze(NOON + timedelta(seconds=3))
        await _type(hers, thread_id)
        again = await his.receive()

    assert first["type"] == again["type"] == "typing"


async def test_forty_a_minute_in_all_then_nothing_is_read(
    app: FastAPI,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread)
    man_id, woman_id = man.id, woman.id

    async with (
        connect(app, await _path(test_redis, woman_id), origin=ORIGIN) as hers,
        connect(app, await _path(test_redis, man_id), origin=ORIGIN) as his,
    ):
        await _subscribed(test_redis, man_id)
        # Thirty-nine Threads that aren't hers, each a first: each counts.
        for _ in range(39):
            await _type(hers, uuid.uuid4())
        await _type(hers, thread_id)
        fortieth = await his.receive()

        clock.freeze(NOON + timedelta(seconds=3))
        await _type(hers, thread_id)
        await _settled(hers)
        await his.nothing()

        clock.freeze(NOON + timedelta(seconds=61))
        await _type(hers, thread_id)
        later = await his.receive()

    assert fortieth["type"] == later["type"] == "typing"


@pytest.mark.parametrize("who_blocks", ["her", "him"])
async def test_nothing_is_heard_across_a_block(
    db: AsyncSession,
    app: FastAPI,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
    who_blocks: str,
) -> None:
    man, woman, thread_id = await _pair(make_user, make_thread)
    if who_blocks == "her":
        await block(db, woman, man)
    else:
        await block(db, man, woman)
    man_id, woman_id = man.id, woman.id

    async with (
        connect(app, await _path(test_redis, woman_id), origin=ORIGIN) as hers,
        connect(app, await _path(test_redis, man_id), origin=ORIGIN) as his,
    ):
        await _subscribed(test_redis, man_id)
        await _type(hers, thread_id)
        await _settled(hers)
        await his.nothing()


@pytest.mark.parametrize(
    "data",
    [
        None,
        "not an object",
        {},
        {"thread_id": 7},
        {"thread_id": "not-a-uuid"},
        {"thread_id": "someone else's"},
        {"thread_id": "none"},
    ],
)
async def test_anything_else_is_dropped_and_the_socket_stays_open(
    app: FastAPI,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
    data: Any,
) -> None:
    man, woman, _ = await _pair(make_user, make_thread)
    stranger, _ = await make_user(Gender.FEMALE)
    theirs = await make_thread(man, stranger)
    if isinstance(data, dict) and data.get("thread_id") == "someone else's":
        data = {"thread_id": str(theirs.id)}
    elif isinstance(data, dict) and data.get("thread_id") == "none":
        data = {"thread_id": str(uuid.uuid4())}
    man_id, woman_id = man.id, woman.id

    async with (
        connect(app, await _path(test_redis, woman_id), origin=ORIGIN) as hers,
        connect(app, await _path(test_redis, man_id), origin=ORIGIN) as his,
    ):
        await _subscribed(test_redis, man_id)
        envelope: dict[str, Any] = {"type": "typing", "id": str(uuid.uuid4())}
        if data is not None:
            envelope["data"] = data
        await hers.send(envelope)
        await _settled(hers)
        await his.nothing()


# --- The short session (D-670) ---------------------------------------------------


async def test_the_opener_hands_its_connection_back_and_publishes_after(
    app: FastAPI, test_redis: Redis
) -> None:
    """The real opener, not the tests' stand-in: a session that holds a pooled
    connection while it lives and none once it closes, its committed events
    published after."""
    opened = session_opener(Namespace(app=app))  # type: ignore[arg-type]
    user_id = uuid.uuid4()
    pubsub = test_redis.pubsub()
    await pubsub.subscribe(f"user:{user_id}")
    pool = app.state.engine.sync_engine.pool
    try:
        async with opened() as session, session.begin():
            await session.connection()
            held = pool.checkedout()
            events.queue(session, user_id, "typing", {"thread_id": "t"})
        after = pool.checkedout()
        message = None
        for _ in range(50):
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=0.1
            )
            if message is not None:
                break
    finally:
        await pubsub.aclose()  # type: ignore[no-untyped-call]

    assert (held, after) == (1, 0)
    assert message is not None
    assert b'"type": "typing"' in message["data"]
