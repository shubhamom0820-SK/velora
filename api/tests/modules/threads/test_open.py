"""`POST /v1/threads` (T-7.1): a Thread from a match or as a private message,
one per pair; a man pays once (5 from a match, 8 for a private message), a
woman never; an expired Thread refuses him and is returned to her (D-097);
whom you may reach (D-493, D-550), every refusal `NOT_FOUND`; the Thread's
hours read from `app_config` (D-097, P-150); a woman's daily limits (D-098)."""

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
from app.core.enums import FraudBand, Gender, Role, Seeking, ThreadOrigin, ThreadStatus
from app.core.security import make_access_token
from app.modules.matches.models import Match
from app.modules.messages.models import Message
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Profile
from app.modules.safety.models import FraudEvent
from app.modules.threads import repository as threads_repository
from app.modules.threads.models import Thread
from app.modules.threads.router import OPENS_PER_MINUTE
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import banded, bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST


async def _match(db: AsyncSession, a: User, b: User) -> Match:
    low, high = sorted((a.id, b.id))
    match = Match(user_low=low, user_high=high)
    db.add(match)
    await db.flush()
    return match


async def _open(client: AsyncClient, token: str, **body: Any) -> Response:
    return await client.post(
        "/v1/threads",
        json={
            key: value if isinstance(value, int) else str(value)
            for key, value in body.items()
        },
        headers=bearer(token),
    )


async def _opened(client: AsyncClient, token: str, **body: Any) -> dict[str, Any]:
    response = await _open(client, token, **body)
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    assert set(found) == {
        "id",
        "origin",
        "status",
        "other_user_id",
        "expires_at",
        "knotted_at",
        "i_tied",
        "last_message_at",
        "created_at",
    }
    return found


async def _ledger(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int, Any]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta, LedgerEntry.ref_id)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at)
    )
    return [(str(reason), delta, ref) for reason, delta, ref in rows]


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    found = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _threads_between(
    db: AsyncSession, a: uuid.UUID, b: uuid.UUID
) -> list[Thread]:
    low, high = sorted((a, b))
    rows = await db.scalars(
        select(Thread)
        .where(Thread.user_low == low, Thread.user_high == high)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def _config(db: AsyncSession, key: str, value: int) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
        {"k": key, "v": str(value)},
    )


# --- From a match ---------------------------------------------------------------


async def test_a_man_opens_from_a_match_for_five_and_she_is_told(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(NOON)
    man, token = await make_user(credits=12)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    match = await _match(db, man, woman)

    body = await _opened(client, token, match_id=match.id, shown_price=5)

    [thread] = await _threads_between(db, man_id, woman_id)
    assert body["id"] == str(thread.id)
    assert body["origin"] == "match"
    assert body["status"] == "active"
    assert body["other_user_id"] == str(woman.id)
    assert body["i_tied"] is False
    # thread_hours, read from app_config (24 today; P-150 makes it 1).
    assert thread.expires_at == NOON + timedelta(hours=24)
    assert datetime.fromisoformat(body["expires_at"]) == thread.expires_at
    assert thread.opened_by == man.id
    assert await _ledger(db, man_id) == [("thread_open", -5, thread.id)]
    assert await _balance(db, man_id) == 7
    await db.refresh(match)
    assert match.thread_id == thread.id
    notes = await db.scalars(
        select(Notification).where(Notification.user_id == woman.id)
    )
    payload = {"thread_id": str(thread.id), "user_id": str(man.id)}
    assert [(n.kind, n.payload) for n in notes] == [("thread", payload)]
    # make_user's grant was the test's own, never published (P-64).
    assert [(e.user_id, e.type, e.data) for e in published] == [
        (man.id, "wallet.updated", {"balance": 7}),
        (woman.id, "thread.opened", payload),
    ]


async def test_the_hours_are_the_settings_never_a_number(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """D-097's hour arrives as a row: nothing in the code says 24."""
    clock.freeze(NOON)
    await _config(db, "thread_hours", 1)
    man, token = await make_user(credits=5)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    match = await _match(db, man, woman)

    await _opened(client, token, match_id=match.id, shown_price=5)

    [thread] = await _threads_between(db, man_id, woman_id)
    assert thread.expires_at == NOON + timedelta(hours=1)


async def test_a_woman_opens_free_and_sees_no_countdown(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    man_id = man.id
    woman, token = await make_user(Gender.FEMALE)
    woman_id = woman.id
    match = await _match(db, man, woman)

    body = await _opened(client, token, match_id=match.id)

    [thread] = await _threads_between(db, man_id, woman_id)
    assert thread.expires_at is not None  # it runs; she isn't shown it (D-554)
    assert body["expires_at"] is None
    assert body["other_user_id"] == str(man.id)
    count = await db.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.user_id == woman.id)
    )
    assert count == 0


async def test_a_second_open_returns_the_thread_and_charges_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    match = await _match(db, man, woman)

    first = await _opened(client, token, match_id=match.id, shown_price=5)
    second = await _opened(client, token, match_id=match.id, shown_price=5)

    assert second["id"] == first["id"]
    assert len(await _threads_between(db, man_id, woman_id)) == 1
    assert [r for r, _, _ in await _ledger(db, man_id)] == ["thread_open"]
    assert await _balance(db, man_id) == 5


async def test_a_man_without_the_velas_opens_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=4)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    match = await _match(db, man, woman)

    response = await _open(client, token, match_id=match.id, shown_price=5)

    assert response.status_code == 402
    assert error(response)["code"] == "INSUFFICIENT_CREDITS"
    assert error(response)["details"] == {"required": 5, "balance": 4}
    assert await _threads_between(db, man_id, woman_id) == []
    await db.refresh(match)
    assert match.thread_id is None


@pytest.mark.parametrize(("shown", "price"), [(None, 5), (4, 5), (6, 5)])
async def test_a_thread_at_a_price_he_wasnt_shown_opens_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    shown: int | None,
    price: int,
) -> None:
    """P-56, D-600: "Open thread · 5 Velas" and anything else charged is
    refused, nothing opened, nothing debited, the price now in `details`."""
    man, token = await make_user(credits=12)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    match = await _match(db, man, woman)
    body: dict[str, Any] = {"match_id": match.id}
    if shown is not None:
        body["shown_price"] = shown

    response = await _open(client, token, **body)

    assert response.status_code == 409
    assert error(response)["code"] == "PRICE_CHANGED"
    assert error(response)["details"] == {"price": price}
    assert await _threads_between(db, man_id, woman_id) == []
    assert await _ledger(db, man_id) == []


async def test_a_private_message_shown_at_the_wrong_price_sends_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=12)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id

    response = await _open(
        client, token, user_id=woman_id, first_message="Hi", shown_price=5
    )

    assert error(response)["code"] == "PRICE_CHANGED"
    assert error(response)["details"] == {"price": 8}
    assert await _threads_between(db, man_id, woman_id) == []


# --- An expired Thread (D-097) --------------------------------------------------


async def test_an_expired_thread_refuses_him(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread, db: AsyncSession
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    match = await _match(db, man, woman)
    await make_thread(man, woman, status="expired")

    response = await _open(client, token, match_id=match.id)

    assert response.status_code == 410
    assert error(response)["code"] == "THREAD_EXPIRED"
    assert await _ledger(db, man_id) == []


async def test_a_thread_past_its_hour_refuses_him_before_the_cron(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    db: AsyncSession,
    clock: ModuleType,
) -> None:
    """Expired by the clock, not the status column (D-560)."""
    clock.freeze(NOON)
    man, token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)
    match = await _match(db, man, woman)
    thread = await make_thread(man, woman)
    thread.expires_at = NOON - timedelta(minutes=1)
    await db.flush()

    response = await _open(client, token, match_id=match.id)

    assert response.status_code == 410
    assert error(response)["code"] == "THREAD_EXPIRED"


async def test_an_expired_thread_is_returned_to_her(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread, db: AsyncSession
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    match = await _match(db, man, woman)
    thread = await make_thread(man, woman, status="expired")

    body = await _opened(client, token, match_id=match.id)

    assert body["id"] == str(thread.id)
    assert body["status"] == "expired"


@pytest.mark.parametrize("status", ["active", "knotted"])
async def test_a_live_thread_is_returned_and_its_match_pointed_at_it(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    db: AsyncSession,
    status: str,
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(woman, man, status=status, origin="dm")
    match = await _match(db, man, woman)

    body = await _opened(client, token, match_id=match.id)

    assert body["id"] == str(thread.id)
    assert await _ledger(db, man_id) == []
    await db.refresh(match)
    assert match.thread_id == thread.id


# --- A private message (D-231) ----------------------------------------------------


async def test_a_private_message_costs_him_eight_and_never_expires(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id

    body = await _opened(
        client,
        token,
        user_id=woman.id,
        shown_price=8,
        first_message="Hi, call me on 9876543210",
    )

    [thread] = await _threads_between(db, man_id, woman_id)
    assert body["origin"] == "dm"
    assert thread.origin is ThreadOrigin.DM
    assert thread.status is ThreadStatus.ACTIVE
    assert thread.expires_at is None and body["expires_at"] is None
    assert await _ledger(db, man_id) == [("dm_open", -8, thread.id)]
    [message] = await db.scalars(select(Message).where(Message.thread_id == thread.id))
    # Masked from the first message on (D-030); the original for moderation.
    assert message.body == "Hi, call me on ••••••••••"
    assert message.masked is True
    assert message.body_raw == "Hi, call me on 9876543210"
    assert thread.message_count == 1
    assert thread.last_message_at == message.created_at
    sent = [(e.user_id, e.type) for e in published if e.type != "wallet.updated"]
    assert sorted(sent, key=str) == sorted(
        [
            (woman.id, "thread.opened"),
            (man.id, "message.new"),
            (woman.id, "message.new"),
        ],
        key=str,
    )


async def test_the_message_event_never_carries_the_original(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    man, token = await make_user(credits=10)
    woman, _ = await make_user(Gender.FEMALE)

    await _opened(
        client, token, user_id=woman.id, shown_price=8, first_message="mail priya@x.com"
    )

    new = [e for e in published if e.type == "message.new"]
    assert len(new) == 2
    for each in new:
        assert "priya@x.com" not in each.envelope()
        assert each.data["message"]["mine"] is (each.user_id == man.id)


async def test_a_woman_sends_a_private_message_free(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    man_id = man.id
    woman, token = await make_user(Gender.FEMALE)
    woman_id = woman.id

    await _opened(client, token, user_id=man.id, first_message="Hello")

    assert len(await _threads_between(db, man_id, woman_id)) == 1
    assert await _ledger(db, woman_id) == []


async def test_a_private_message_needs_her_to_want_his_gender(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Unlike a link to her profile, a private message asks what swipes ask:
    each wanting the other's gender (D-550)."""
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    await db.execute(
        update(Profile).where(Profile.user_id == woman.id).values(seeking=Seeking.WOMEN)
    )

    response = await _open(client, token, user_id=woman.id, first_message="Hi")

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert await _ledger(db, man_id) == []


async def test_a_rejected_first_message_opens_nothing_and_is_recorded(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id

    response = await _open(
        client, token, user_id=woman.id, first_message="send money first"
    )

    assert response.status_code == 422
    assert error(response)["code"] == "MESSAGE_REJECTED"
    assert error(response)["details"] == {"rule": "solicitation"}
    assert await _threads_between(db, man_id, woman_id) == []
    assert await _ledger(db, man_id) == []
    signals = await db.execute(
        select(FraudEvent.signal, FraudEvent.weight, FraudEvent.meta).where(
            FraudEvent.user_id == man_id
        )
    )
    assert signals.tuples().all() == [("message_rejected", 0, {"rule": "solicitation"})]


# --- Whom: every refusal NOT_FOUND --------------------------------------------------


async def _refused(response: Response) -> None:
    assert response.status_code == 404, response.text
    assert error(response) == {"code": "NOT_FOUND", "message": "Not found."}


async def test_someone_elses_match_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(credits=10)
    other, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    match = await _match(db, other, woman)

    await _refused(await _open(client, token, match_id=match.id))
    await _refused(await _open(client, token, match_id=uuid.uuid4()))


@pytest.mark.parametrize("who_blocks", ["him", "her"])
async def test_a_block_either_way_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, who_blocks: str
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    match = await _match(db, man, woman)
    if who_blocks == "him":
        await block(db, man, woman)
    else:
        await block(db, woman, man)

    match_id, woman_id = match.id, woman.id

    await _refused(await _open(client, token, match_id=match_id))
    await _refused(await _open(client, token, user_id=woman_id, first_message="Hi"))
    assert await _ledger(db, man_id) == []


async def test_a_frozen_or_unfinished_person_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=10)
    frozen, _ = await make_user(Gender.FEMALE)
    await banded(db, frozen, FraudBand.FREEZE)
    unfinished, _ = await make_user(Gender.FEMALE, onboarded=False)
    frozen_match = (await _match(db, man, frozen)).id
    unfinished_match = (await _match(db, man, unfinished)).id

    await _refused(await _open(client, token, match_id=frozen_match))
    await _refused(await _open(client, token, match_id=unfinished_match))
    await _refused(await _open(client, token, user_id=uuid.uuid4(), first_message="x"))


async def test_yourself_is_not_found(client: AsyncClient, make_user: MakeUser) -> None:
    man, token = await make_user(credits=10)

    await _refused(await _open(client, token, user_id=man.id, first_message="Hi"))


async def test_onboarding_comes_first(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user(onboarded=False)

    response = await _open(client, token, match_id=uuid.uuid4())

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"match_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4())},
        {"match_id": str(uuid.uuid4()), "first_message": "Hi"},
        {"user_id": str(uuid.uuid4())},
        {"first_message": "Hi"},
        {"user_id": str(uuid.uuid4()), "first_message": ""},
        {"user_id": str(uuid.uuid4()), "first_message": "   "},
        {"user_id": str(uuid.uuid4()), "first_message": "x" * 501},
        {"match_id": str(uuid.uuid4()), "price": 5},
        {"match_id": str(uuid.uuid4()), "shown_price": -1},
        {"match_id": str(uuid.uuid4()), "shown_price": "five"},
    ],
)
async def test_a_bad_body_is_a_validation_error(
    client: AsyncClient, make_user: MakeUser, body: dict[str, Any]
) -> None:
    _, token = await make_user(credits=10)

    response = await client.post("/v1/threads", json=body, headers=bearer(token))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_opens_are_rate_limited(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user()
    for _ in range(OPENS_PER_MINUTE):
        await _open(client, token, match_id=uuid.uuid4())

    response = await _open(client, token, match_id=uuid.uuid4())

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


# --- A woman's daily limits (D-098) ---------------------------------------------------


async def test_she_opens_with_so_many_new_men_a_day(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    await _config(db, "women_new_men_daily_limit", 2)
    woman, token = await make_user(Gender.FEMALE)
    woman_id = woman.id
    men = [(await make_user())[0] for _ in range(3)]
    matches = [await _match(db, man, woman) for man in men]

    await _opened(client, token, match_id=matches[0].id)
    await _opened(client, token, user_id=men[1].id, first_message="Hi")
    refused = await _open(client, token, match_id=matches[2].id)
    # The Thread she already has is no new man.
    again = await _open(client, token, match_id=matches[0].id)

    assert refused.status_code == 429
    assert error(refused)["code"] == "RATE_LIMITED"
    # Until the next IST midnight, 12 hours on.
    assert error(refused)["details"] == {"retry_after_s": 12 * 3600}
    assert again.status_code == 200
    assert await _threads_between(db, men[2].id, woman_id) == []

    clock.advance(timedelta(hours=12))
    fresh = make_access_token(
        woman_id, Role.USER, make_test_settings(), auth_time=clock.now()
    )
    await _opened(client, fresh, match_id=matches[2].id)


async def test_she_sends_so_many_private_messages_a_day(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await _config(db, "women_private_messages_daily_limit", 1)
    _, token = await make_user(Gender.FEMALE)
    first, _ = await make_user()
    second, _ = await make_user()

    await _opened(client, token, user_id=first.id, first_message="Hi")
    refused = await _open(client, token, user_id=second.id, first_message="Hi")

    assert refused.status_code == 429
    assert error(refused)["code"] == "RATE_LIMITED"


async def test_her_places_come_back_when_nothing_is_written(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _config(db, "women_new_men_daily_limit", 1)
    await _config(db, "women_private_messages_daily_limit", 1)
    _, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    real_add = threads_repository.add
    calls = 0

    async def fail_once(*args: Any, **kwargs: Any) -> Thread:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("the insert failed")
        return await real_add(*args, **kwargs)

    monkeypatch.setattr(threads_repository, "add", fail_once)

    man_id = man.id
    failed = await _open(client, token, user_id=man_id, first_message="Hi")
    await _opened(client, token, user_id=man_id, first_message="Hi")

    assert failed.status_code == 500


async def test_men_and_women_to_women_have_no_such_limit(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await _config(db, "women_new_men_daily_limit", 0)
    await _config(db, "women_private_messages_daily_limit", 5)
    _, man_token = await make_user(credits=20)
    woman, token = await make_user(Gender.FEMALE)
    other, _ = await make_user(Gender.FEMALE)
    await db.execute(
        update(Profile)
        .where(Profile.user_id.in_([woman.id, other.id]))
        .values(seeking=Seeking.EVERYONE)
    )
    match = await _match(db, woman, other)

    await _opened(
        client, man_token, user_id=woman.id, first_message="Hi", shown_price=8
    )
    await _opened(client, token, match_id=match.id)
