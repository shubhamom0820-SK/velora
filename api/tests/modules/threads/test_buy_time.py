"""`POST /v1/threads/{id}/reopen` and `/extend` (T-7.6): what time costs him
and what it buys (D-097, D-098, D-250, D-253, D-560), the price he was shown
(P-56, D-600), a retried tap charged once (D-077), and who can't buy at all
(D-642)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, ThreadStatus
from app.modules.threads.models import Thread
from app.modules.threads.router import TIME_BUYS_PER_MINUTE
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST
PRICE = {"reopen": 2, "extend": 10}


async def _buy(
    client: AsyncClient,
    token: str,
    thread_id: uuid.UUID,
    what: str,
    *,
    key: str | None = None,
    shown_price: int | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    sent = {**bearer(token), "Idempotency-Key": key or uuid.uuid4().hex}
    if headers is not None:
        sent = headers
    return await client.post(
        f"/v1/threads/{thread_id}/{what}",
        json=None if shown_price is None else {"shown_price": shown_price},
        headers=sent,
    )


async def _bought(
    client: AsyncClient, token: str, thread_id: uuid.UUID, what: str, **kw: Any
) -> dict[str, Any]:
    kw.setdefault("shown_price", PRICE[what])
    response = await _buy(client, token, thread_id, what, **kw)
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def _thread(db: AsyncSession, thread_id: uuid.UUID) -> Thread:
    found = await db.scalar(
        select(Thread)
        .where(Thread.id == thread_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _set(db: AsyncSession, thread_id: uuid.UUID, **values: Any) -> None:
    await db.execute(update(Thread).where(Thread.id == thread_id).values(**values))


async def _config(db: AsyncSession, key: str, value: int) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
        {"k": key, "v": str(value)},
    )


async def _charges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    return [(str(reason), delta) for reason, delta in rows]


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert balance is not None
    return balance


# --- Extend ---------------------------------------------------------------------------


async def test_extend_adds_a_day_to_what_is_left(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    """T-7.6's answer 4: 4 hours left and an Extend is 28, no paid hour lost;
    the warning cleared (D-560); one `thread_extend` debit (D-251)."""
    clock.freeze(NOON)
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man)
    thread_id = thread.id
    await _set(
        db,
        thread_id,
        expires_at=NOON + timedelta(hours=4),
        expiry_warned_at=NOON - timedelta(minutes=1),
    )

    body = await _bought(client, token, thread_id, "extend")

    after = await _thread(db, thread_id)
    assert after.expires_at == NOON + timedelta(hours=28)
    assert after.expiry_warned_at is None
    assert after.status is ThreadStatus.ACTIVE
    assert datetime.fromisoformat(body["expires_at"]) == after.expires_at
    assert await _charges(db, man_id) == [("thread_extend", -10)]
    # Nothing reaches her: she is never shown that time was bought (D-097).
    assert [(e.user_id, e.type) for e in published] == [(man_id, "wallet.updated")]


async def test_a_second_extend_stacks_on_the_first(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """D-250: as often as he likes, each on top of what is left."""
    clock.freeze(NOON)
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    thread_id = thread.id
    await _set(db, thread_id, expires_at=NOON + timedelta(minutes=30))

    await _bought(client, token, thread_id, "extend")
    clock.freeze(NOON + timedelta(minutes=10))
    await _bought(client, token, thread_id, "extend")

    after = await _thread(db, thread_id)
    assert after.expires_at == NOON + timedelta(minutes=30, hours=48)
    assert await _charges(db, man_id) == [
        ("thread_extend", -10),
        ("thread_extend", -10),
    ]


@pytest.mark.parametrize("how", ["status", "clock"])
async def test_extend_from_expired_is_one_debit_and_a_day_from_now(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    how: str,
) -> None:
    """D-253: the same 10 re-opens it, never 2 and then 10; expired by its
    status, or by the clock before the sweep has caught it up (D-560)."""
    clock.freeze(NOON)
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    if how == "status":
        thread = await make_thread(man, woman, status="expired")
        thread_id = thread.id
    else:
        thread = await make_thread(man, woman)
        thread_id = thread.id
        await _set(db, thread_id, expires_at=NOON - timedelta(minutes=5))

    body = await _bought(client, token, thread_id, "extend", shown_price=10)

    after = await _thread(db, thread_id)
    assert after.status is ThreadStatus.ACTIVE
    assert after.expires_at == NOON + timedelta(hours=24)
    assert body["status"] == "active"
    assert await _charges(db, man_id) == [("thread_extend", -10)]
    assert await _balance(db, man_id) == 15


@pytest.mark.parametrize("shown", [2, 12, None])
async def test_extend_from_expired_compares_its_ten_and_nothing_else(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    shown: int | None,
) -> None:
    """P-56, D-600: never 2 + 10, never the re-open's 2; an absent price is 0.
    Nothing is charged or written."""
    clock.freeze(NOON)
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id
    before = (await _thread(db, thread_id)).expires_at

    response = await _buy(client, token, thread_id, "extend", shown_price=shown)

    assert response.status_code == 409
    assert error(response)["code"] == "PRICE_CHANGED"
    assert error(response)["details"] == {"price": 10}
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == (ThreadStatus.EXPIRED, before)
    assert await _charges(db, man_id) == []
    assert await _balance(db, man_id) == 25


# --- Re-open --------------------------------------------------------------------------


@pytest.mark.parametrize("how", ["status", "clock"])
async def test_reopen_is_two_and_an_hour_from_now(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    how: str,
) -> None:
    """D-097 step 4, D-098; T-7.6's answer 1: the hour starts now, never from
    her last message, so the 2 he paid buys an hour."""
    clock.freeze(NOON)
    man, token = await make_user(credits=5)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    if how == "status":
        thread = await make_thread(man, woman, status="expired")
        thread_id = thread.id
    else:
        thread = await make_thread(man, woman)
        thread_id = thread.id
        await _set(
            db,
            thread_id,
            expires_at=NOON - timedelta(hours=3),
            expiry_warned_at=NOON - timedelta(hours=3, minutes=10),
        )

    body = await _bought(client, token, thread_id, "reopen")

    after = await _thread(db, thread_id)
    assert after.status is ThreadStatus.ACTIVE
    assert after.expires_at == NOON + timedelta(hours=1)
    assert after.expiry_warned_at is None
    assert body["status"] == "active"
    assert await _charges(db, man_id) == [("thread_reopen", -2)]


async def test_reopen_reads_the_setting_never_a_number(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    await _config(db, "thread_hours", 3)
    man, token = await make_user(credits=5)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    await _bought(client, token, thread_id, "reopen")

    assert (await _thread(db, thread_id)).expires_at == NOON + timedelta(hours=3)


async def test_extend_reads_the_setting_never_a_number(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    await _config(db, "thread_extend_hours", 30)
    man, token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    await _bought(client, token, thread_id, "extend")

    assert (await _thread(db, thread_id)).expires_at == NOON + timedelta(hours=30)


async def test_reopening_a_live_thread_returns_it_and_charges_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """D-642: it is already what he asked for, as `POST /threads` returns an
    existing Thread."""
    clock.freeze(NOON)
    man, token = await make_user(credits=5)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    thread_id = thread.id
    await _set(db, thread_id, expires_at=NOON + timedelta(minutes=1))

    body = await _bought(client, token, thread_id, "reopen")

    assert body["status"] == "active"
    assert (await _thread(db, thread_id)).expires_at == NOON + timedelta(minutes=1)
    assert await _charges(db, man_id) == []


@pytest.mark.parametrize("shown", [10, None])
async def test_a_reopen_he_wasnt_shown_the_price_of_buys_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    shown: int | None,
) -> None:
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    response = await _buy(client, token, thread_id, "reopen", shown_price=shown)

    assert response.status_code == 409
    assert error(response)["details"] == {"price": 2}
    assert (await _thread(db, thread_id)).status is ThreadStatus.EXPIRED
    assert await _charges(db, man_id) == []


async def test_after_a_reopen_his_send_goes_through(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    man, token = await make_user(credits=5)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    def send() -> Any:
        return client.post(
            f"/v1/threads/{thread_id}/messages",
            json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hi"},
            headers=bearer(token),
        )

    refused = await send()
    await _bought(client, token, thread_id, "reopen")
    sent = await send()

    assert error(refused)["code"] == "THREAD_EXPIRED"
    assert sent.status_code == 200, sent.text


# --- Both: a tap sent twice, and who can't buy --------------------------------------


@pytest.mark.parametrize("what", ["reopen", "extend"])
async def test_the_same_key_again_is_charged_once_and_moves_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    what: str,
) -> None:
    """D-077: the client's key fills the wallet's event, so a retried tap
    returns the Thread as the first left it."""
    clock.freeze(NOON)
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    first = await _bought(client, token, thread_id, what, key="tap-0001")
    clock.freeze(NOON + timedelta(minutes=5))
    again = await _bought(client, token, thread_id, what, key="tap-0001")

    assert again == first
    hours = 1 if what == "reopen" else 24
    assert (await _thread(db, thread_id)).expires_at == NOON + timedelta(hours=hours)
    assert len(await _charges(db, man_id)) == 1


async def test_one_key_for_two_threads_buys_twice(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """The event names the Thread too: a key sent again for another Thread is
    another purchase, never the first one's Thread returned for it."""
    man, token = await make_user(credits=25)
    man_id = man.id
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    first = await make_thread(man, one, status="expired")
    first_id = first.id
    second = await make_thread(man, two, status="expired")
    second_id = second.id

    await _bought(client, token, first_id, "extend", key="tap-0001")
    body = await _bought(client, token, second_id, "extend", key="tap-0001")

    assert body["id"] == str(second_id)
    assert (await _thread(db, second_id)).status is ThreadStatus.ACTIVE
    assert await _charges(db, man_id) == [
        ("thread_extend", -10),
        ("thread_extend", -10),
    ]


@pytest.mark.parametrize("what", ["reopen", "extend"])
@pytest.mark.parametrize("status", ["active", "expired"])
async def test_a_woman_buys_nothing_and_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    what: str,
    status: str,
) -> None:
    """D-097: she is never charged and never shown it (D-642)."""
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    woman_id = woman.id
    thread = await make_thread(man, woman, status=status)
    thread_id = thread.id
    before = await _thread(db, thread_id)
    expected = (before.status, before.expires_at)

    response = await _buy(client, token, thread_id, what, shown_price=0)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == expected
    assert await _charges(db, woman_id) == []


@pytest.mark.parametrize("what", ["reopen", "extend"])
@pytest.mark.parametrize(
    ("status", "origin"),
    [("knotted", "match"), ("active", "dm")],
    ids=["a knot", "a private message"],
)
async def test_what_has_no_hour_cant_be_bought(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    what: str,
    status: str,
    origin: str,
) -> None:
    """D-642: a Knot is permanent (D-003), a private message never expires
    (D-550)."""
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status=status, origin=origin)
    thread_id = thread.id

    response = await _buy(client, token, thread_id, what, shown_price=PRICE[what])

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == (ThreadStatus(status), None)
    assert await _charges(db, man_id) == []


@pytest.mark.parametrize("what", ["reopen", "extend"])
async def test_without_the_velas_nothing_is_bought(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    what: str,
) -> None:
    man, token = await make_user(credits=1)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    response = await _buy(client, token, thread_id, what, shown_price=PRICE[what])

    assert response.status_code == 402
    assert error(response)["code"] == "INSUFFICIENT_CREDITS"
    assert (await _thread(db, thread_id)).status is ThreadStatus.EXPIRED


@pytest.mark.parametrize("what", ["reopen", "extend"])
async def test_someone_elses_thread_is_not_found(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread, what: str
) -> None:
    one, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    _, stranger = await make_user(credits=25)
    thread = await make_thread(one, woman, status="expired")
    thread_id = thread.id

    elses = await _buy(client, stranger, thread_id, what, shown_price=PRICE[what])
    nobodys = await _buy(client, stranger, uuid.uuid4(), what, shown_price=2)

    assert [r.status_code for r in (elses, nobodys)] == [404, 404]
    assert error(elses)["code"] == "NOT_FOUND"


@pytest.mark.parametrize("who_blocks", ["him", "her"])
async def test_a_block_either_way_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    who_blocks: str,
) -> None:
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id
    if who_blocks == "him":
        await block(db, man, woman)
    else:
        await block(db, woman, man)

    response = await _buy(client, token, thread_id, "extend", shown_price=10)

    assert response.status_code == 404
    assert await _charges(db, man_id) == []


@pytest.mark.parametrize("what", ["reopen", "extend"])
@pytest.mark.parametrize("key", [None, "short", "has space in it", "x" * 65])
async def test_a_missing_or_malformed_key_is_a_validation_error(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    what: str,
    key: str | None,
) -> None:
    man, token = await make_user(credits=25)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id
    headers = (
        bearer(token) if key is None else {**bearer(token), "Idempotency-Key": key}
    )

    response = await _buy(
        client, token, thread_id, what, shown_price=PRICE[what], headers=headers
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await _charges(db, man_id) == []


async def test_a_body_naming_anything_else_is_a_validation_error(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=25)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="expired")
    thread_id = thread.id

    response = await client.post(
        f"/v1/threads/{thread_id}/extend",
        json={"shown_price": 10, "hours": 48},
        headers={**bearer(token), "Idempotency-Key": "tap-0001"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize("what", ["reopen", "extend"])
async def test_signed_out_is_refused(
    db: AsyncSession, client: AsyncClient, what: str
) -> None:
    response = await client.post(
        f"/v1/threads/{uuid.uuid4()}/{what}",
        headers={"Idempotency-Key": "tap-0001"},
    )

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_buying_time_is_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Re-opens and Extends share one limit."""
    _, token = await make_user()
    for n in range(TIME_BUYS_PER_MINUTE):
        what = "reopen" if n % 2 else "extend"
        await _buy(client, token, uuid.uuid4(), what, shown_price=2)

    response = await _buy(client, token, uuid.uuid4(), "extend", shown_price=10)

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
