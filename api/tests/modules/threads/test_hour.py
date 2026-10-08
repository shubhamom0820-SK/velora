"""The 1-hour Thread over time (T-7.6, D-097 and its amendment, D-560): her
message restarts the hour and his never does; an Extend ends on her last
message's hour, not a fresh one; and the minute's sweep agrees with the clock.

The clock moves through each story; every request carries a token minted at
that moment, as a signed-in client's would be."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core import events
from app.core.enums import Gender, Role, ThreadStatus
from app.core.security import make_access_token
from app.modules.threads import service as threads_service
from app.modules.threads.models import Thread
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST


def _token(user_id: uuid.UUID) -> str:
    """Signed in just now, by the frozen clock."""
    return make_access_token(
        user_id, Role.USER, make_test_settings(), auth_time=core_clock.now()
    )


async def _send(
    client: AsyncClient, user_id: uuid.UUID, thread_id: uuid.UUID
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hello"},
        headers=bearer(_token(user_id)),
    )


async def _sent(client: AsyncClient, user_id: uuid.UUID, thread_id: uuid.UUID) -> None:
    response = await _send(client, user_id, thread_id)
    assert response.status_code == 200, response.text


async def _extend(
    client: AsyncClient, user_id: uuid.UUID, thread_id: uuid.UUID
) -> None:
    response = await client.post(
        f"/v1/threads/{thread_id}/extend",
        json={"shown_price": 10},
        headers={**bearer(_token(user_id)), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text


async def _thread(db: AsyncSession, thread_id: uuid.UUID) -> Thread:
    found = await db.scalar(
        select(Thread)
        .where(Thread.id == thread_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _sweep(db: AsyncSession) -> int:
    """The minute's expiry, on the test's session (`tests/workers` runs it
    through the worker's own loop)."""
    if db.in_transaction():
        await db.commit()
    expired = await threads_service.expire_batch(db)
    events.take_committed(db)
    return expired


async def _pair(
    make_user: MakeUser, make_thread: MakeThread, db: AsyncSession, **kw: Any
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """(him, her, their Thread), opened by him at NOON with an hour to run: he
    writes free (D-551), so only the hour is in question."""
    man, _ = await make_user(credits=kw.pop("credits", 0))
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    ids = (man.id, woman.id, thread.id)
    await db.execute(
        update(Thread)
        .where(Thread.id == ids[2])
        .values(expires_at=NOON + timedelta(hours=1))
    )
    return ids


async def test_his_messages_never_keep_it_open_and_hers_do(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """D-097's amendment (a): he writes every 59 minutes and the Thread still
    expires an hour after her last message, never later."""
    clock.freeze(NOON)
    man, woman, thread = await _pair(make_user, make_thread, db)
    clock.freeze(NOON + timedelta(minutes=1))
    await _sent(client, woman, thread)  # her last: the hour now ends at 13:01
    await _sent(client, man, thread)

    clock.freeze(NOON + timedelta(minutes=1 + 59))
    await _sent(client, man, thread)
    clock.freeze(NOON + timedelta(minutes=1 + 60))
    refused = await _send(client, man, thread)

    assert error(refused)["code"] == "THREAD_EXPIRED"
    assert (await _thread(db, thread)).expires_at == NOON + timedelta(minutes=61)
    assert await _sweep(db) == 1
    assert (await _thread(db, thread)).status is ThreadStatus.EXPIRED


async def test_her_message_restarts_the_hour(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    _, woman, thread = await _pair(make_user, make_thread, db)

    clock.freeze(NOON + timedelta(minutes=50))
    await _sent(client, woman, thread)
    clock.freeze(NOON + timedelta(minutes=100))
    still = await _sweep(db)

    assert still == 0
    assert (await _thread(db, thread)).expires_at == NOON + timedelta(minutes=110)


async def test_an_extend_ends_on_her_last_hour_when_she_went_quiet(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """D-097's amendment (d): Extend bought 24 hours, never 25. Her last
    message is over an hour old when it ends, so it expires that instant."""
    clock.freeze(NOON)
    man, woman, thread = await _pair(make_user, make_thread, db, credits=10)
    clock.freeze(NOON + timedelta(minutes=10))
    await _sent(client, woman, thread)  # 13:10
    await _extend(client, man, thread)  # 13:10 + 24 h
    ends = NOON + timedelta(minutes=70, hours=24)

    clock.freeze(NOON + timedelta(hours=23))
    await _sent(client, woman, thread)  # not in its last hour: moves nothing
    clock.freeze(ends - timedelta(seconds=1))
    await _sent(client, man, thread)
    clock.freeze(ends)
    refused = await _send(client, man, thread)

    assert error(refused)["code"] == "THREAD_EXPIRED"
    assert (await _thread(db, thread)).expires_at == ends
    assert await _sweep(db) == 1


async def test_her_message_in_an_extends_last_hour_carries_it_on(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """(d)'s other side: she wrote in the Extend's last hour, so the Thread
    runs an hour from her message, past the Extend's end."""
    clock.freeze(NOON)
    man, woman, thread = await _pair(make_user, make_thread, db, credits=10)
    await _extend(client, man, thread)  # 13:00 + 24 h
    ends = NOON + timedelta(hours=25)

    clock.freeze(ends - timedelta(minutes=20))
    await _sent(client, woman, thread)
    clock.freeze(ends + timedelta(minutes=1))
    await _sent(client, man, thread)

    assert await _sweep(db) == 0
    assert (await _thread(db, thread)).expires_at == ends + timedelta(minutes=40)


async def test_past_its_hour_before_the_sweep_hers_revives_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """D-560: in the minute before the sweep, his send is refused and her
    message is delivered and moves nothing (D-097 step 4: it stays expired
    until he re-opens); then the sweep expires it."""
    clock.freeze(NOON)
    man, woman, thread = await _pair(make_user, make_thread, db)

    clock.freeze(NOON + timedelta(hours=1, seconds=30))
    his = await _send(client, man, thread)
    hers = await _send(client, woman, thread)
    swept = await _sweep(db)

    assert error(his)["code"] == "THREAD_EXPIRED"
    assert hers.status_code == 200
    after = await _thread(db, thread)
    assert (after.status, after.expires_at) == (
        ThreadStatus.EXPIRED,
        NOON + timedelta(hours=1),
    )
    assert swept == 1
