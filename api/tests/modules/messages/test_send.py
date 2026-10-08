"""`POST /v1/threads/{id}/messages` (T-7.3): an expired Thread refuses him
and takes hers (D-097), by the clock (D-560); what his messages cost (D-098,
D-250, D-231); her message moves the hour on and his never does (D-097's
amendment); masked while the Thread is young and refused for abuse or asking
for money (D-030, D-552); a retried send stored once; nothing to a deleted
account (D-555); her daily limits (D-553)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.clock import now as clock_now
from app.core.enums import Gender, ThreadStatus, UserStatus
from app.modules.messages import service as messages_service
from app.modules.messages.models import Message
from app.modules.messages.router import SENDS_PER_MINUTE
from app.modules.safety.models import FraudEvent
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST


async def _send(
    client: AsyncClient,
    token: str,
    thread_id: uuid.UUID,
    body: str = "Hello",
    *,
    client_msg_id: uuid.UUID | None = None,
    **extra: Any,
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(client_msg_id or uuid.uuid4()),
            "kind": "text",
            "body": body,
            **extra,
        },
        headers=bearer(token),
    )


async def _sent(
    client: AsyncClient,
    token: str,
    thread_id: uuid.UUID,
    body: str = "Hello",
    **kw: Any,
) -> dict[str, Any]:
    response = await _send(client, token, thread_id, body, **kw)
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def _charges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    return [(str(reason), delta) for reason, delta in rows]


async def _thread(db: AsyncSession, thread_id: uuid.UUID) -> Thread:
    found = await db.scalar(
        select(Thread)
        .where(Thread.id == thread_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _messages(db: AsyncSession, thread_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count()).select_from(Message).where(Message.thread_id == thread_id)
    )
    return count or 0


async def _config(db: AsyncSession, key: str, value: int) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
        {"k": key, "v": str(value)},
    )


async def _expires(db: AsyncSession, thread: Thread, at: datetime) -> None:
    await db.execute(
        update(Thread)
        .where(Thread.id == thread.id)
        .values(expires_at=at, expiry_warned_at=at - timedelta(minutes=10))
    )


# --- A message ---------------------------------------------------------------------


async def test_a_message_is_stored_counted_and_both_told(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    man_id, woman_id, thread_id = man.id, woman.id, thread.id
    events.take_committed(db)
    client_msg_id = uuid.uuid4()

    body = await _sent(
        client, token, thread_id, "Hi there", client_msg_id=client_msg_id
    )

    [row] = await db.scalars(select(Message).where(Message.thread_id == thread_id))
    assert body == {
        "id": str(row.id),
        "thread_id": str(thread_id),
        "kind": "text",
        "body": "Hi there",
        "masked": False,
        "duration_s": None,
        "mine": True,
        "from_deleted_account": False,
        "locked": False,
        "read_at": None,
        "created_at": row.created_at.isoformat().replace("+00:00", "Z"),
        "client_msg_id": str(client_msg_id),
    }
    refreshed = await _thread(db, thread_id)
    assert refreshed.message_count == 1
    assert refreshed.last_message_at == row.created_at
    told = {
        e.user_id: e.data for e in events.take_committed(db) if e.type == "message.new"
    }
    assert set(told) == {man_id, woman_id}
    assert told[woman_id]["message"]["mine"] is True
    assert told[man_id]["message"]["mine"] is False
    assert told[man_id]["message"]["client_msg_id"] is None


async def test_a_retried_send_is_stored_once_and_charged_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, origin="dm")
    man_id, thread_id = man.id, thread.id
    client_msg_id = uuid.uuid4()

    first = await _sent(client, token, thread_id, client_msg_id=client_msg_id)
    again = await _sent(client, token, thread_id, client_msg_id=client_msg_id)

    assert again == first
    assert await _messages(db, thread_id) == 1
    assert await _charges(db, man_id) == [("dm_message", -2)]


async def test_a_message_id_used_in_another_thread_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    first = (await make_thread(man, one)).id
    second = (await make_thread(man, two)).id
    client_msg_id = uuid.uuid4()

    await _sent(client, token, first, client_msg_id=client_msg_id)
    response = await _send(client, token, second, client_msg_id=client_msg_id)

    assert response.status_code == 409
    assert error(response)["code"] == "ALREADY_EXISTS"


# --- What his messages cost --------------------------------------------------------


async def test_the_opener_writes_free(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id
    man_id = man.id

    await _sent(client, token, thread_id)
    await _sent(client, token, thread_id)

    assert await _charges(db, man_id) == []


async def test_answering_her_costs_him_the_re_open_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-250: when she wrote first, he pays the 2-Vela re-open to answer."""
    man, token = await make_user(credits=10)
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man)).id
    man_id = man.id

    await _sent(client, her_token, thread_id)
    await _sent(client, token, thread_id)
    await _sent(client, token, thread_id)

    assert await _charges(db, man_id) == [("thread_reopen", -2)]
    key = await db.scalar(
        select(LedgerEntry.idempotency_key).where(
            LedgerEntry.user_id == man_id, LedgerEntry.reason == "thread_reopen"
        )
    )
    assert key == f"{man_id}:thread_reopen:answer:{thread_id}"


async def test_writing_first_where_she_opened_costs_him_the_open(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-097 step 1: a man's first message opens a Thread, for 5."""
    man, token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man)).id
    man_id = man.id

    await _sent(client, token, thread_id)
    await _sent(client, token, thread_id)

    assert await _charges(db, man_id) == [("thread_open", -5)]


async def test_a_private_message_costs_him_two_each_and_her_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=10)
    woman, her_token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man, origin="dm")).id
    man_id, woman_id = man.id, woman.id

    await _sent(client, her_token, thread_id)
    one = await _sent(client, token, thread_id)
    two = await _sent(client, token, thread_id)

    refs = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta, LedgerEntry.ref_id)
        .where(LedgerEntry.user_id == man_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    assert sorted(refs.tuples().all(), key=str) == sorted(
        [
            ("dm_message", -2, uuid.UUID(one["id"])),
            ("dm_message", -2, uuid.UUID(two["id"])),
        ],
        key=str,
    )
    assert await _charges(db, woman_id) == []


@pytest.mark.parametrize("origin", ["match", "dm"])
async def test_a_knot_is_free(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    origin: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man, status="knotted", origin=origin)).id
    man_id = man.id

    await _sent(client, token, thread_id)

    assert await _charges(db, man_id) == []


async def test_without_the_velas_nothing_is_sent(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=1)
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(woman, man, origin="dm")).id

    response = await _send(client, token, thread_id)

    assert response.status_code == 402
    assert error(response)["code"] == "INSUFFICIENT_CREDITS"
    assert await _messages(db, thread_id) == 0


# --- The hour (D-097, D-560) ----------------------------------------------------------


async def test_her_message_moves_the_hour_on_and_clears_the_warning(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    await _config(db, "thread_hours", 1)
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _expires(db, thread, NOON + timedelta(minutes=10))

    await _sent(client, token, thread.id)

    moved = await _thread(db, thread.id)
    assert moved.expires_at == NOON + timedelta(hours=1)
    assert moved.expiry_warned_at is None


async def test_his_message_never_moves_the_hour(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    clock.freeze(NOON)
    await _config(db, "thread_hours", 1)
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _expires(db, thread, NOON + timedelta(minutes=10))

    await _sent(client, token, thread.id)

    assert (await _thread(db, thread.id)).expires_at == NOON + timedelta(minutes=10)


async def test_her_message_never_cuts_a_longer_hour_short(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """An Extend's day isn't shortened by her message (D-560's max)."""
    clock.freeze(NOON)
    await _config(db, "thread_hours", 1)
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _expires(db, thread, NOON + timedelta(hours=20))

    await _sent(client, token, thread.id)

    assert (await _thread(db, thread.id)).expires_at == NOON + timedelta(hours=20)


@pytest.mark.parametrize("how", ["status", "clock"])
async def test_an_expired_thread_refuses_him_and_takes_hers_moving_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    how: str,
) -> None:
    """Expired by its status, or by the clock before the cron has caught the
    status up (D-560): the same either way."""
    clock.freeze(NOON)
    man, token = await make_user(credits=10)
    woman, her_token = await make_user(Gender.FEMALE)
    if how == "status":
        thread = await make_thread(man, woman, status="expired")
    else:
        thread = await make_thread(man, woman)
        await _expires(db, thread, NOON - timedelta(minutes=1))
    thread_id = thread.id
    before = (await _thread(db, thread_id)).expires_at

    his = await _send(client, token, thread_id)
    hers = await _send(client, her_token, thread_id)

    assert his.status_code == 410
    assert error(his)["code"] == "THREAD_EXPIRED"
    assert hers.status_code == 200
    after = await _thread(db, thread_id)
    assert after.expires_at == before
    assert after.status is (
        ThreadStatus.EXPIRED if how == "status" else ThreadStatus.ACTIVE
    )
    assert await _messages(db, thread_id) == 1


async def test_a_private_message_never_takes_an_hour(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman, origin="dm")).id

    await _sent(client, token, thread_id)

    assert (await _thread(db, thread_id)).expires_at is None


# --- Masking and refusals (D-030, D-552) ------------------------------------------------


async def test_contact_details_are_masked_in_the_first_twenty(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    young = (await make_thread(man, woman, messages=19)).id

    body = await _sent(client, token, young, "call 9876543210")

    assert body["body"] == "call ••••••••••"
    assert body["masked"] is True
    assert "body_raw" not in body
    stored = await db.scalar(
        select(Message.body_raw).where(Message.id == uuid.UUID(body["id"]))
    )
    assert stored == "call 9876543210"


async def test_from_the_twenty_first_nothing_is_masked(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    older = (await make_thread(man, woman, messages=20)).id

    body = await _sent(client, token, older, "call 9876543210")

    assert (body["body"], body["masked"]) == ("call 9876543210", False)


@pytest.mark.parametrize(
    ("text_", "rule"), [("you bitch", "abuse"), ("gpay kar do", "solicitation")]
)
async def test_abuse_and_asking_for_money_are_refused_and_kept_as_a_signal(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    text_: str,
    rule: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id
    man_id = man.id

    response = await _send(client, token, thread_id, text_)

    assert response.status_code == 422
    assert error(response)["code"] == "MESSAGE_REJECTED"
    assert error(response)["details"] == {"rule": rule}
    assert await _messages(db, thread_id) == 0
    signals = await db.execute(
        select(FraudEvent.signal, FraudEvent.meta).where(FraudEvent.user_id == man_id)
    )
    assert signals.tuples().all() == [("message_rejected", {"rule": rule})]


# --- Who may send, and what ---------------------------------------------------------------


async def test_nothing_reaches_a_deleted_account(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id
    await db.execute(
        update(User)
        .where(User.id == woman.id)
        .values(status=UserStatus.DELETED, deleted_requested_at=clock_now())
    )

    response = await _send(client, token, thread_id)

    assert response.status_code == 410
    assert error(response)["code"] == "ACCOUNT_DELETED"
    assert await _messages(db, thread_id) == 0


async def test_someone_elses_thread_is_not_found(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    _, stranger = await make_user()
    thread_id = (await make_thread(man, woman)).id

    for target in (thread_id, uuid.uuid4()):
        response = await _send(client, stranger, target)
        assert response.status_code == 404
        assert error(response)["code"] == "NOT_FOUND"


async def test_a_voice_note_isnt_sendable_yet(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    thread_id = (await make_thread(man, woman)).id

    response = await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "kind": "voice",
            "media_key": "voice/x.webm",
            "duration_s": 10,
        },
        headers=bearer(token),
    )

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "text"},
        {"kind": "text", "body": ""},
        {"kind": "text", "body": "   "},
        {"kind": "text", "body": "x" * 2001},
        {"kind": "text", "body": "hi", "media_key": "voice/x.webm"},
        {"kind": "system", "body": "hi"},
        {"kind": "text", "body": "hi", "price": 0},
        {"body": "hi"},
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
        f"/v1/threads/{thread_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), **body},
        headers=bearer(token),
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_sends_are_rate_limited(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user()
    for _ in range(SENDS_PER_MINUTE):
        await _send(client, token, uuid.uuid4())

    response = await _send(client, token, uuid.uuid4())

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


# --- Her daily limits (D-553) --------------------------------------------------------------


async def test_writing_first_to_a_man_counts_among_her_new_men(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    await _config(db, "women_new_men_daily_limit", 1)
    woman, token = await make_user(Gender.FEMALE)
    one, _ = await make_user()
    two, _ = await make_user()
    first = (await make_thread(one, woman)).id
    second = (await make_thread(two, woman)).id

    await _sent(client, token, first)
    await _sent(client, token, first)  # the same man, already counted
    refused = await _send(client, token, second)

    assert refused.status_code == 429
    assert error(refused)["code"] == "RATE_LIMITED"


async def test_answering_him_isnt_writing_first(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    await _config(db, "women_new_men_daily_limit", 0)
    woman, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    thread_id = (await make_thread(man, woman, messages=1)).id

    await _sent(client, token, thread_id)


async def test_her_private_messages_are_counted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    await _config(db, "women_private_messages_daily_limit", 2)
    woman, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    thread_id = (await make_thread(man, woman, origin="dm", messages=1)).id

    await _sent(client, token, thread_id)
    await _sent(client, token, thread_id)
    refused = await _send(client, token, thread_id)

    assert refused.status_code == 429
    assert error(refused)["code"] == "RATE_LIMITED"


async def test_a_retry_takes_no_place(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    await _config(db, "women_private_messages_daily_limit", 2)
    woman, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    thread_id = (await make_thread(man, woman, origin="dm", messages=1)).id
    client_msg_id = uuid.uuid4()

    await _sent(client, token, thread_id, client_msg_id=client_msg_id)
    await _sent(client, token, thread_id, client_msg_id=client_msg_id)
    await _sent(client, token, thread_id)


async def test_a_failed_send_gives_her_place_back(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _config(db, "women_private_messages_daily_limit", 1)
    woman, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    thread_id = (await make_thread(man, woman, origin="dm", messages=1)).id
    real_write = messages_service.write_text
    calls = 0

    async def fail_once(*args: Any, **kwargs: Any) -> Message:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("the insert failed")
        return await real_write(*args, **kwargs)

    monkeypatch.setattr(messages_service, "write_text", fail_once)

    failed = await _send(client, token, thread_id)
    await _sent(client, token, thread_id)

    assert failed.status_code == 500
