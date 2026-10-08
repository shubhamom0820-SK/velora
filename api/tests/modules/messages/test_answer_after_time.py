"""D-641 (T-7.6): once he has paid a re-open or an Extend in a Thread she
opened, his first message there costs nothing more. D-097 step 4 says he pays
2 "to re-open the Thread and reply", and D-253 that he never pays 2 and then
10; T-7.3's answer price (D-551) would otherwise charge him a second time."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.wallet.models import LedgerEntry
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer

pytestmark = pytest.mark.usefixtures("test_redis")

PRICE = {"reopen": 2, "extend": 10}


async def _buy(
    client: AsyncClient, token: str, thread_id: uuid.UUID, what: str
) -> None:
    response = await client.post(
        f"/v1/threads/{thread_id}/{what}",
        json={"shown_price": PRICE[what]},
        headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text


async def _send(
    client: AsyncClient, token: str, thread_id: uuid.UUID, **extra: Any
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "kind": "text",
            "body": "Hello",
            **extra,
        },
        headers=bearer(token),
    )


async def _charges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    return [(str(reason), delta) for reason, delta in rows]


@pytest.mark.parametrize("what", ["reopen", "extend"])
async def test_after_he_paid_from_expired_answering_her_is_free(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    what: str,
) -> None:
    """She opened and wrote; the hour ran out before he answered."""
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man, status="expired", messages=1)
    thread_id = thread.id

    await _buy(client, token, thread_id, what)
    sent = await _send(client, token, thread_id)

    assert sent.status_code == 200, sent.text
    reason = "thread_reopen" if what == "reopen" else "thread_extend"
    assert await _charges(db, man_id) == [(reason, -PRICE[what])]


async def test_after_an_extend_on_a_live_thread_answering_her_is_free(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man, messages=1)
    thread_id = thread.id

    await _buy(client, token, thread_id, "extend")
    sent = await _send(client, token, thread_id)

    assert sent.status_code == 200, sent.text
    assert await _charges(db, man_id) == [("thread_extend", -10)]


async def test_after_a_reopen_where_nobody_wrote_writing_first_is_free(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """She opened without a word and it ran out: his 2 re-opened it, so his
    first message isn't charged the 5 that writing first would be."""
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man, status="expired")
    thread_id = thread.id

    await _buy(client, token, thread_id, "reopen")
    sent = await _send(client, token, thread_id)

    assert sent.status_code == 200, sent.text
    assert await _charges(db, man_id) == [("thread_reopen", -2)]


async def test_time_bought_in_another_thread_answers_nothing_here(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """Only a re-open or an Extend naming this Thread counts."""
    man, token = await make_user(credits=25)
    man_id = man.id
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    elsewhere = await make_thread(one, man, status="expired")
    elsewhere_id = elsewhere.id
    here = await make_thread(two, man, messages=1)
    here_id = here.id

    await _buy(client, token, elsewhere_id, "reopen")
    sent = await _send(client, token, here_id, shown_price=2)

    assert sent.status_code == 200, sent.text
    assert await _charges(db, man_id) == [
        ("thread_reopen", -2),
        ("thread_reopen", -2),
    ]
