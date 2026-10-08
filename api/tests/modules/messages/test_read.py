"""`POST /v1/threads/{id}/read` (T-7.5): the other person's messages read up
to the one named, each once; `message.read` to them alone, with no countdown
and no price whoever reads (D-554); nothing before my clearing; nothing across
a block, in someone else's Thread, or up to a message I can't see."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core import events
from app.core.enums import Gender, MessageKind, ThreadStatus
from app.modules.messages.models import Message
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error
from tests.modules.realtime.test_typing import ORIGIN, _path, _subscribed
from tests.ws import connect

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST


async def _say(
    db: AsyncSession, thread: Thread, sender: User, *, ago: timedelta
) -> uuid.UUID:
    """A text from `sender`, `ago` before now; its id."""
    message = Message(
        thread_id=thread.id,
        sender_id=sender.id,
        kind=MessageKind.TEXT,
        body="Hello",
        client_msg_id=uuid.uuid4(),
        created_at=core_clock.now() - ago,
    )
    db.add(message)
    thread.message_count += 1
    await db.flush()
    return message.id


async def _read(
    client: AsyncClient, token: str, thread_id: uuid.UUID, up_to: Any
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/read",
        json={"up_to_message_id": str(up_to)},
        headers=bearer(token),
    )


async def _read_at(db: AsyncSession, *ids: uuid.UUID) -> list[datetime | None]:
    rows = await db.execute(
        select(Message.id, Message.read_at)
        .where(Message.id.in_(ids))
        .execution_options(populate_existing=True)
    )
    found: dict[uuid.UUID, datetime | None] = {row.id: row.read_at for row in rows}
    return [found[each] for each in ids]


def _reads(published: list[events.Event]) -> list[events.Event]:
    return [each for each in published if each.type == "message.read"]


# --- Reading --------------------------------------------------------------------


@pytest.mark.parametrize("reader", ["him", "her"])
async def test_their_messages_up_to_the_one_named_are_read_and_they_alone_told(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
    clock: ModuleType,
    reader: str,
) -> None:
    clock.freeze(NOON)
    man, his_token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    me, them, token = (
        (man, woman, his_token) if reader == "him" else (woman, man, her_token)
    )
    first = await _say(db, thread, them, ago=timedelta(minutes=5))
    mine = await _say(db, thread, me, ago=timedelta(minutes=4))
    second = await _say(db, thread, them, ago=timedelta(minutes=3))
    later = await _say(db, thread, them, ago=timedelta(minutes=1))
    thread_id, them_id = thread.id, them.id
    clock.freeze(NOON + timedelta(minutes=2))

    response = await _read(client, token, thread_id, second)

    assert response.status_code == 204
    assert response.content == b""
    at = NOON + timedelta(minutes=2)
    assert await _read_at(db, first, mine, second, later) == [at, None, at, None]
    [told] = _reads(published)
    assert told.user_id == them_id
    # Exactly these: no countdown, no price, on either side (D-554).
    assert told.data == {
        "thread_id": str(thread_id),
        "up_to_message_id": str(second),
        "read_at": "2026-10-08T06:32:00Z",
    }


async def test_the_receipt_reaches_his_socket(
    db: AsyncSession,
    app: FastAPI,
    client: AsyncClient,
    test_redis: Redis,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """End to end: she reads by REST, and his socket hears it."""
    man, _ = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    his_message = await _say(db, thread, man, ago=timedelta(minutes=1))
    thread_id, man_id = thread.id, man.id

    async with connect(app, await _path(test_redis, man_id), origin=ORIGIN) as his:
        await _subscribed(test_redis, man_id)
        response = await _read(client, her_token, thread_id, his_message)
        envelope = await his.receive()

    assert response.status_code == 204
    assert envelope["type"] == "message.read"
    assert envelope["data"]["up_to_message_id"] == str(his_message)


async def test_up_to_my_own_message_names_their_newest_before_it(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    hers = await _say(db, thread, woman, ago=timedelta(minutes=3))
    mine = await _say(db, thread, man, ago=timedelta(minutes=1))

    response = await _read(client, token, thread.id, mine)

    assert response.status_code == 204
    [told] = _reads(published)
    assert told.data["up_to_message_id"] == str(hers)


async def test_a_read_at_once_set_never_moves_and_a_second_read_tells_nobody(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    hers = await _say(db, thread, woman, ago=timedelta(minutes=1))
    thread_id = thread.id

    assert (await _read(client, token, thread_id, hers)).status_code == 204
    clock.freeze(NOON + timedelta(minutes=10))
    again = await _read(client, token, thread_id, hers)

    assert again.status_code == 204
    assert await _read_at(db, hers) == [NOON]
    assert len(_reads(published)) == 1


async def test_my_own_messages_are_never_marked(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    mine = await _say(db, thread, man, ago=timedelta(minutes=1))

    response = await _read(client, token, thread.id, mine)

    assert response.status_code == 204
    assert await _read_at(db, mine) == [None]
    assert _reads(published) == []


async def test_nothing_before_my_clearing_is_marked(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    before = await _say(db, thread, woman, ago=timedelta(hours=2))
    after = await _say(db, thread, woman, ago=timedelta(minutes=1))
    db.add(
        ThreadClear(
            user_id=man.id,
            thread_id=thread.id,
            cleared_at=core_clock.now() - timedelta(hours=1),
        )
    )
    await db.flush()

    response = await _read(client, token, thread.id, after)

    assert response.status_code == 204
    before_at, after_at = await _read_at(db, before, after)
    # Hidden from him, so never seen: "Not seen yet" stays true for her.
    assert before_at is None
    assert after_at is not None


async def test_the_list_counts_them_read(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, ago=timedelta(minutes=2))
    newest = await _say(db, thread, woman, ago=timedelta(minutes=1))
    thread_id = thread.id

    def unread(response: Response) -> int:
        [row] = [r for r in response.json()["items"] if r["id"] == str(thread_id)]
        count: int = row["unread"]
        return count

    before = unread(await client.get("/v1/threads", headers=bearer(token)))
    assert (await _read(client, token, thread_id, newest)).status_code == 204
    after = unread(await client.get("/v1/threads", headers=bearer(token)))

    assert (before, after) == (2, 0)


async def test_an_expired_thread_is_still_read(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status=ThreadStatus.EXPIRED)
    hers = await _say(db, thread, woman, ago=timedelta(minutes=1))

    response = await _read(client, token, thread.id, hers)

    assert response.status_code == 204
    assert await _read_at(db, hers) != [None]
    assert len(_reads(published)) == 1


# --- Refused ----------------------------------------------------------------------


async def _not_found(response: Response) -> None:
    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


@pytest.mark.parametrize("who_blocks", ["me", "them"])
async def test_across_a_block_nothing_is_read_and_nobody_told(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
    who_blocks: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    hers = await _say(db, thread, woman, ago=timedelta(minutes=1))
    if who_blocks == "me":
        await block(db, man, woman)
    else:
        await block(db, woman, man)

    await _not_found(await _read(client, token, thread.id, hers))
    assert await _read_at(db, hers) == [None]
    assert _reads(published) == []


async def test_someone_elses_thread_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    _, stranger = await make_user()
    thread = await make_thread(man, woman)
    hers = await _say(db, thread, woman, ago=timedelta(minutes=1))
    thread_id = thread.id

    await _not_found(await _read(client, stranger, thread_id, hers))
    await _not_found(await _read(client, stranger, uuid.uuid4(), hers))
    assert await _read_at(db, hers) == [None]
    assert _reads(published) == []


async def test_a_message_from_another_thread_or_none_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    other_woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    elsewhere = await make_thread(man, other_woman)
    hers = await _say(db, thread, woman, ago=timedelta(minutes=2))
    theirs = await _say(db, elsewhere, other_woman, ago=timedelta(minutes=1))
    thread_id = thread.id

    await _not_found(await _read(client, token, thread_id, theirs))
    await _not_found(await _read(client, token, thread_id, uuid.uuid4()))
    assert await _read_at(db, hers, theirs) == [None, None]
    assert _reads(published) == []


async def test_a_message_before_my_clearing_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    before = await _say(db, thread, woman, ago=timedelta(hours=2))
    db.add(
        ThreadClear(
            user_id=man.id,
            thread_id=thread.id,
            cleared_at=core_clock.now() - timedelta(hours=1),
        )
    )
    await db.flush()

    await _not_found(await _read(client, token, thread.id, before))
    assert await _read_at(db, before) == [None]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"up_to_message_id": "not-a-uuid"},
        {"up_to_message_id": str(uuid.uuid4()), "read_at": "2026-10-08T06:30:00Z"},
    ],
)
async def test_a_bad_body_is_a_validation_error(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    body: dict[str, Any],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id

    response = await client.post(
        f"/v1/threads/{thread_id}/read", json=body, headers=bearer(token)
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_signed_out_and_unfinished_onboarding_are_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, unfinished = await make_user(onboarded=False)
    target = f"/v1/threads/{uuid.uuid4()}/read"
    body = {"up_to_message_id": str(uuid.uuid4())}

    signed_out = await client.post(target, json=body)
    early = await client.post(target, json=body, headers=bearer(unfinished))

    assert signed_out.status_code == 401
    assert error(signed_out)["code"] == "AUTH_REQUIRED"
    assert early.status_code == 403
    assert error(early)["code"] == "ONBOARDING_INCOMPLETE"
