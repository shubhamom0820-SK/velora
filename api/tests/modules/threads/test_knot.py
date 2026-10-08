"""`POST` and `DELETE /v1/threads/{id}/knot` (T-7.7): each of the two taps,
free, and the second tap makes a Knot (D-003), on a live or an expired Thread;
untying gives a Thread from a match a fresh hour and a private message none
(D-550, D-560); who is told what (D-770)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core import events
from app.core.enums import Gender, Role, ThreadStatus, UserStatus
from app.core.security import make_access_token
from app.modules.notifications.models import Notification
from app.modules.threads import service as threads_service
from app.modules.threads.models import Thread
from app.modules.threads.router import KNOTS_PER_MINUTE
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 12:00 IST


def _token(user_id: uuid.UUID) -> str:
    """Signed in just now, by the (frozen) clock."""
    return make_access_token(
        user_id, Role.USER, make_test_settings(), auth_time=core_clock.now()
    )


async def _knot(
    client: AsyncClient,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    *,
    untie: bool = False,
) -> Response:
    return await client.request(
        "DELETE" if untie else "POST",
        f"/v1/threads/{thread_id}/knot",
        headers=bearer(_token(user_id)),
    )


async def _knotted(
    client: AsyncClient,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    *,
    untie: bool = False,
) -> dict[str, Any]:
    response = await _knot(client, user_id, thread_id, untie=untie)
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def _send(
    client: AsyncClient, user_id: uuid.UUID, thread_id: uuid.UUID, price: int = 0
) -> Response:
    return await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "kind": "text",
            "body": "Hello",
            "shown_price": price,
        },
        headers=bearer(_token(user_id)),
    )


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


async def _notified(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, Any]]:
    rows = await db.execute(
        select(Notification.kind, Notification.payload)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at, Notification.id)
    )
    return [(kind, payload) for kind, payload in rows]


async def _charges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    return [(str(reason), delta) for reason, delta in rows]


def _seen(published: list[events.Event]) -> list[tuple[uuid.UUID, str]]:
    return [(e.user_id, e.type) for e in published if e.type.startswith("knot.")]


async def _pair(
    make_user: MakeUser,
    make_thread: MakeThread,
    *,
    status: str = "active",
    origin: str = "match",
    credits: int = 0,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """(him, her, their Thread, opened by him)."""
    man, _ = await make_user(credits=credits)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status=status, origin=origin)
    return man.id, woman.id, thread.id


# --- Tying ------------------------------------------------------------------------------


async def test_one_tap_asks_the_other_and_nothing_else_moves(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread)
    before = await _thread(db, thread_id)
    expires_at = before.expires_at

    body = await _knotted(client, man, thread_id)

    assert body["i_tied"] is True
    assert body["status"] == "active"
    assert body["knotted_at"] is None
    after = await _thread(db, thread_id)
    assert after.status is ThreadStatus.ACTIVE
    assert after.expires_at == expires_at
    assert after.knotted_at is None
    taps = {after.user_low: after.low_knot_at, after.user_high: after.high_knot_at}
    assert taps == {man: NOON, woman: None}
    assert _seen(published) == [(woman, "knot.requested")]
    request = next(e for e in published if e.type == "knot.requested")
    assert request.data == {"thread_id": str(thread_id), "user_id": str(man)}
    payload = {"thread_id": str(thread_id), "user_id": str(man)}
    assert await _notified(db, woman) == [("knot_requested", payload)]
    assert await _notified(db, man) == []
    # Her own view: she hasn't tapped.
    hers = await client.get(f"/v1/threads/{thread_id}", headers=bearer(_token(woman)))
    assert hers.json()["i_tied"] is False


async def test_a_second_tap_of_ones_own_tells_nobody_again(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread)
    await _knotted(client, man, thread_id)
    clock.freeze(NOON + timedelta(minutes=5))

    body = await _knotted(client, man, thread_id)

    assert body["i_tied"] is True
    after = await _thread(db, thread_id)
    tap = after.low_knot_at if man == after.user_low else after.high_knot_at
    assert tap == NOON
    assert _seen(published) == [(woman, "knot.requested")]
    assert [kind for kind, _ in await _notified(db, woman)] == ["knot_requested"]


async def test_tap_untie_tap_asks_her_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    """D-770: untying a Thread that isn't a Knot changes nothing, so a pending
    tap stays and tapping again can't ask her twice."""
    man, woman, thread_id = await _pair(make_user, make_thread)

    await _knotted(client, man, thread_id)
    untied = await _knotted(client, man, thread_id, untie=True)
    await _knotted(client, man, thread_id)

    assert untied["i_tied"] is True
    assert _seen(published) == [(woman, "knot.requested")]
    assert [kind for kind, _ in await _notified(db, woman)] == ["knot_requested"]


@pytest.mark.parametrize("first", ["him", "her"])
async def test_the_second_tap_makes_a_knot(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    published: list[events.Event],
    first: str,
) -> None:
    """D-003: permanent and free; no expiry, ever, and nothing charged."""
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread, credits=25)
    await _set(db, thread_id, expiry_warned_at=NOON)
    one, two = (man, woman) if first == "him" else (woman, man)
    await _knotted(client, one, thread_id)
    clock.freeze(NOON + timedelta(minutes=3))

    body = await _knotted(client, two, thread_id)

    tied_at = NOON + timedelta(minutes=3)
    assert body["status"] == "knotted"
    assert body["expires_at"] is None
    assert datetime.fromisoformat(body["knotted_at"]) == tied_at
    assert body["i_tied"] is True
    after = await _thread(db, thread_id)
    assert after.status is ThreadStatus.KNOTTED
    assert after.knotted_at == tied_at
    assert after.expires_at is None
    assert after.expiry_warned_at is None
    assert _seen(published) == [
        (two, "knot.requested"),
        (two, "knot.accepted"),
        (one, "knot.accepted"),
    ]
    accepted = [e.data for e in published if e.type == "knot.accepted"]
    assert (
        accepted
        == [{"thread_id": str(thread_id), "knotted_at": tied_at.isoformat()}] * 2
    )
    assert [kind for kind, _ in await _notified(db, one)] == ["knot_accepted"]
    assert [kind for kind, _ in await _notified(db, two)] == ["knot_requested"]
    assert await _charges(db, man) == []


async def test_tapping_a_knot_returns_it_and_tells_nobody(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, woman, thread_id = await _pair(make_user, make_thread, status="knotted")
    before = await _thread(db, thread_id)
    knotted_at = before.knotted_at

    body = await _knotted(client, woman, thread_id)

    assert body["status"] == "knotted"
    assert (await _thread(db, thread_id)).knotted_at == knotted_at
    assert _seen(published) == []
    assert await _notified(db, man) == []


@pytest.mark.parametrize("by", ["status", "clock"])
async def test_an_expired_thread_ties_straight_into_a_knot(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    by: str,
) -> None:
    """T-7.7: a tap works on an expired Thread, and both convert it directly,
    whether the sweep caught its status up or only the clock says so
    (D-560). Then his send passes, free."""
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread)
    if by == "status":
        await _set(
            db,
            thread_id,
            status=ThreadStatus.EXPIRED,
            expires_at=NOON - timedelta(hours=1),
        )
    else:
        await _set(db, thread_id, expires_at=NOON - timedelta(minutes=1))

    await _knotted(client, man, thread_id)
    alone = await _send(client, man, thread_id)
    assert alone.status_code == 410
    assert error(alone)["code"] == "THREAD_EXPIRED"

    body = await _knotted(client, woman, thread_id)

    assert body["status"] == "knotted"
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == (ThreadStatus.KNOTTED, None)
    sent = await _send(client, man, thread_id)
    assert sent.status_code == 200, sent.text
    assert await _charges(db, man) == []


async def test_a_knot_has_no_hour_for_anyone_to_move(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """Once knotted: her message sets no expiry, Extend and re-open are
    `NOT_ALLOWED` (D-642), and the minute's sweep passes it by, however long
    it has been."""
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread, credits=25)
    await _knotted(client, man, thread_id)
    await _knotted(client, woman, thread_id)

    clock.freeze(NOON + timedelta(days=30))
    sent = await _send(client, woman, thread_id)
    assert sent.status_code == 200, sent.text
    for what, price in (("extend", 10), ("reopen", 2)):
        bought = await client.post(
            f"/v1/threads/{thread_id}/{what}",
            json={"shown_price": price},
            headers={**bearer(_token(man)), "Idempotency-Key": uuid.uuid4().hex},
        )
        assert bought.status_code == 422
        assert error(bought)["code"] == "NOT_ALLOWED"
    if db.in_transaction():
        await db.commit()
    await threads_service.expire_batch(db)
    events.take_committed(db)

    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == (ThreadStatus.KNOTTED, None)
    assert await _charges(db, man) == []


async def test_a_private_messages_knot_makes_his_messages_free(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    """D-550, D-551: each of his private messages costs 2 until knotted."""
    man, woman, thread_id = await _pair(make_user, make_thread, origin="dm", credits=25)
    await _knotted(client, woman, thread_id)
    await _knotted(client, man, thread_id)

    sent = await _send(client, man, thread_id)

    assert sent.status_code == 200, sent.text
    assert await _charges(db, man) == []


# --- Untying ------------------------------------------------------------------------------


async def test_untying_a_knot_gives_a_fresh_hour_from_the_setting(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    """T-7.7, D-560: `now + thread_hours`, read from `app_config` (3 here, so
    a literal 1 fails), both taps cleared; the other told, no notification
    (D-770); and the hour then runs out as any other."""
    clock.freeze(NOON)
    man, woman, thread_id = await _pair(make_user, make_thread, status="knotted")
    await db.execute(
        text(
            "UPDATE app_config SET value = CAST('3' AS jsonb) WHERE key = 'thread_hours'"
        )
    )
    await _set(db, thread_id, expiry_warned_at=NOON)

    body = await _knotted(client, woman, thread_id, untie=True)

    assert body["status"] == "active"
    assert body["knotted_at"] is None
    assert body["i_tied"] is False
    assert body["expires_at"] is None  # hers: no countdown (D-554)
    after = await _thread(db, thread_id)
    assert after.status is ThreadStatus.ACTIVE
    assert after.expires_at == NOON + timedelta(hours=3)
    assert (after.low_knot_at, after.high_knot_at, after.knotted_at) == (None,) * 3
    assert after.expiry_warned_at is None
    assert _seen(published) == [(man, "knot.untied")]
    untied = next(e for e in published if e.type == "knot.untied")
    assert untied.data == {"thread_id": str(thread_id)}
    assert await _notified(db, man) == []
    assert await _notified(db, woman) == []
    his = await client.get(f"/v1/threads/{thread_id}", headers=bearer(_token(man)))
    assert datetime.fromisoformat(his.json()["expires_at"]) == NOON + timedelta(hours=3)

    clock.freeze(NOON + timedelta(hours=3))
    refused = await _send(client, man, thread_id)
    assert error(refused)["code"] == "THREAD_EXPIRED"


async def test_untying_a_private_message_leaves_it_never_expiring(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
) -> None:
    """D-550: a private message goes back to never expiring, and each of his
    messages costs 2 again (D-551)."""
    clock.freeze(NOON)
    man, _, thread_id = await _pair(
        make_user, make_thread, status="knotted", origin="dm", credits=25
    )

    body = await _knotted(client, man, thread_id, untie=True)

    assert (body["status"], body["expires_at"]) == ("active", None)
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at) == (ThreadStatus.ACTIVE, None)
    clock.freeze(NOON + timedelta(days=30))
    sent = await _send(client, man, thread_id, price=2)
    assert sent.status_code == 200, sent.text
    assert await _charges(db, man) == [("dm_message", -2)]


@pytest.mark.parametrize("status", ["active", "expired"])
async def test_untying_what_isnt_a_knot_changes_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
    status: str,
) -> None:
    """D-770: returned as it is, nobody told; her pending tap stays."""
    man, woman, thread_id = await _pair(make_user, make_thread, status=status)
    await _knotted(client, woman, thread_id)
    published.clear()
    before = await _thread(db, thread_id)
    expected = (
        before.status,
        before.expires_at,
        before.low_knot_at,
        before.high_knot_at,
    )

    response = await _knot(client, man, thread_id, untie=True)

    assert response.status_code == 200
    after = await _thread(db, thread_id)
    assert (after.status, after.expires_at, after.low_knot_at, after.high_knot_at) == (
        expected
    )
    assert published == []


# --- Refusals ------------------------------------------------------------------------------


@pytest.mark.parametrize("untie", [False, True], ids=["tie", "untie"])
async def test_someone_elses_thread_is_not_found(
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
    untie: bool,
) -> None:
    _, _, thread_id = await _pair(make_user, make_thread, status="knotted")
    stranger, _ = await make_user()
    stranger_id = stranger.id

    elses = await _knot(client, stranger_id, thread_id, untie=untie)
    nobodys = await _knot(client, stranger_id, uuid.uuid4(), untie=untie)

    assert [r.status_code for r in (elses, nobodys)] == [404, 404]
    assert error(elses) == error(nobodys)
    assert error(elses)["code"] == "NOT_FOUND"
    assert published == []


@pytest.mark.parametrize("untie", [False, True], ids=["tie", "untie"])
@pytest.mark.parametrize("who_blocks", ["him", "her"])
async def test_a_block_either_way_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
    who_blocks: str,
    untie: bool,
) -> None:
    man, _ = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman, status="knotted" if untie else "active")
    thread_id, man_id = thread.id, man.id
    status = thread.status
    if who_blocks == "him":
        await block(db, man, woman)
    else:
        await block(db, woman, man)

    response = await _knot(client, man_id, thread_id, untie=untie)

    assert response.status_code == 404
    after = await _thread(db, thread_id)
    assert after.status is status
    assert (after.low_knot_at is None) is (not untie)
    assert published == []


async def test_tying_to_a_deleted_account_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    """D-770: nobody is left to tie it back, so nothing is written
    (`ACCOUNT_DELETED`, D-555's code); untying a Knot with them still works."""
    man, woman, thread_id = await _pair(make_user, make_thread)
    _, _, knot_id = await _pair(make_user, make_thread, status="knotted")
    knot = await _thread(db, knot_id)
    knot_man = knot.opened_by
    knot_woman = knot.user_high if knot_man == knot.user_low else knot.user_low
    await db.execute(
        update(User)
        .where(User.id.in_([woman, knot_woman]))
        .values(status=UserStatus.DELETED, deleted_requested_at=clock.now())
    )

    response = await _knot(client, man, thread_id)

    assert response.status_code == 410
    assert error(response)["code"] == "ACCOUNT_DELETED"
    after = await _thread(db, thread_id)
    assert (after.low_knot_at, after.high_knot_at) == (None, None)
    assert await _notified(db, woman) == []
    assert published == []
    untied = await _knotted(client, knot_man, knot_id, untie=True)
    assert untied["status"] == "active"


@pytest.mark.parametrize("untie", [False, True], ids=["tie", "untie"])
async def test_signed_out_is_refused(
    db: AsyncSession, client: AsyncClient, untie: bool
) -> None:
    response = await client.request(
        "DELETE" if untie else "POST", f"/v1/threads/{uuid.uuid4()}/knot"
    )

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_tying_and_untying_are_rate_limited_together(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    user_id = user.id
    for n in range(KNOTS_PER_MINUTE):
        await _knot(client, user_id, uuid.uuid4(), untie=bool(n % 2))

    response = await _knot(client, user_id, uuid.uuid4())

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
