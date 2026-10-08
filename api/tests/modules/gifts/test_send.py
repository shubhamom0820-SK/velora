"""`POST /v1/gifts/send` (T-8.9): a man to a woman he can reach (D-653), fifteen
free sends a week from Monday 00:00 IST (D-231, D-650), then the gift row's
price, debited with the send (rule 5) and only at the price he was shown
(P-56, D-600); the cooldown (D-016); the key (D-653); the Thread linked, never
opened; and she is told.

Every refusal is asserted with nothing written: no send, no ledger row, the
balance as it was, no event and no notification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import FraudBand, Gender, Seeking, ThreadStatus, UserStatus
from app.modules.gifts.router import SENDS_PER_MINUTE
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Profile
from app.modules.threads.models import Thread
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import banded, block, error
from tests.modules.gifts.support import (
    balance,
    ledger,
    notes,
    price,
    send,
    sends_by,
    sent,
    set_config,
    token_for,
)

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # Thursday, 12:00 IST
# The Monday 00:00 IST after NOON, when a new week starts (D-650).
NEXT_MONDAY = datetime(2026, 10, 11, 18, 30, tzinfo=UTC)
FREE = "gift_free_weekly_limit"
COOLDOWN = "gift_same_recipient_cooldown_h"
FOUR = ("coffee", "rose", "chocolate", "teddy")


async def _nothing_written(
    db: AsyncSession,
    man: uuid.UUID,
    credits: int,
    published: list[events.Event],
    woman: uuid.UUID | None = None,
) -> None:
    assert await sends_by(db, man) == []
    assert await ledger(db, man) == []
    assert await balance(db, man) == credits
    assert published == []
    if woman is not None:
        assert await notes(db, woman) == []


def _refused(response: Response, code: str, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    found = error(response)
    assert found["code"] == code
    return found


# --- A send ------------------------------------------------------------------------


async def test_a_free_send_moves_no_vela_and_she_is_told(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(NOON)
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id

    body = await sent(client, token, woman_id, "rose")

    [row] = await sends_by(db, man_id)
    assert body == {
        "id": str(row.id),
        "gift_id": "rose",
        "recipient_id": str(woman_id),
        "credits_charged": 0,
        "thread_id": None,
        "created_at": body["created_at"],
    }
    assert datetime.fromisoformat(body["created_at"]) == NOON == row.created_at
    assert (row.credits_charged, row.thread_id) == (0, None)
    assert await ledger(db, man_id) == []
    payload = {"gift_send_id": str(row.id), "gift_id": "rose", "user_id": str(man_id)}
    assert await notes(db, woman_id) == [("gift", payload)]
    assert [(e.user_id, e.type, e.data) for e in published] == [
        (woman_id, "gift.received", payload)
    ]


@pytest.mark.critical  # 06-TESTING.md #6b
async def test_fifteen_free_sends_write_no_ledger_row_and_the_sixteenth_pays_the_row(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    """D-231: each of the week's fifteen free sends is a row and no ledger
    entry; the sixteenth is exactly one entry, at the price the `gifts` row
    holds (repriced here to a number no default has)."""
    clock.freeze(NOON)
    await price(db, "teddy", 13)
    man, token = await make_user(credits=20)
    man_id = man.id
    women = [(await make_user(Gender.FEMALE))[0].id for _ in range(4)]
    # Sixteen (woman, gift) pairs, so no cooldown stands in the way; `teddy`
    # to the last woman is the sixteenth.
    pairs = [(w, g) for w in women for g in FOUR]

    for n, (woman_id, gift) in enumerate(pairs[:15], start=1):
        await sent(client, token, woman_id, gift, shown=0)
        assert len(await sends_by(db, man_id)) == n
        assert await ledger(db, man_id) == [], f"free send {n} wrote a ledger row"

    woman_id, gift = pairs[15]
    assert gift == "teddy"
    body = await sent(client, token, woman_id, gift, shown=13)

    # One frozen instant, so the rows have no order: compare them as a set.
    rows = await sends_by(db, man_id)
    assert sorted(r.credits_charged for r in rows) == [0] * 15 + [13]
    assert body["credits_charged"] == 13
    assert await ledger(db, man_id) == [("gift", -13, uuid.UUID(body["id"]))]
    assert await balance(db, man_id) == 7
    assert (man_id, "wallet.updated", {"balance": 7}) in [
        (e.user_id, e.type, e.data) for e in published
    ]


async def test_the_week_starts_monday_at_midnight_ist(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """D-650: the last minute of Sunday is still this week, its free send
    used; Monday 00:00 IST brings the week's free sends back."""
    await set_config(db, FREE, 1)
    clock.freeze(NEXT_MONDAY - timedelta(minutes=1))  # Sunday 23:59 IST
    man, token = await make_user(credits=20)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id

    await sent(client, token, woman_id, "coffee", shown=0)
    refused = _refused(
        await send(client, token, woman_id, "rose", shown=0), "PRICE_CHANGED", 409
    )
    assert refused["details"] == {"price": 10}

    clock.freeze(NEXT_MONDAY)
    await sent(client, token, woman_id, "rose", shown=0)

    assert [r.credits_charged for r in await sends_by(db, man_id)] == [0, 0]
    assert await ledger(db, man_id) == []


async def test_the_free_sends_are_the_setting_never_a_number(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    await set_config(db, FREE, 2)
    man, token = await make_user(credits=5)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id

    await sent(client, token, woman_id, "rose", shown=0)
    await sent(client, token, woman_id, "teddy", shown=0)
    await sent(client, token, woman_id, "coffee", shown=5)

    assert sorted(r.credits_charged for r in await sends_by(db, man_id)) == [0, 0, 5]


# --- The price shown (P-56, D-600) ----------------------------------------------------


@pytest.mark.parametrize(
    ("free", "gift", "shown", "now"),
    [
        (0, "rose", None, 10),  # paid, and no price was shown: 0
        (0, "rose", 9, 10),
        (0, "rose", 11, 10),
        (15, "rose", 10, 0),  # free, but shown the gift's price
    ],
)
async def test_a_price_other_than_the_one_shown_is_refused_with_nothing_written(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    free: int,
    gift: str,
    shown: int | None,
    now: int,
) -> None:
    await set_config(db, FREE, free)
    man, token = await make_user(credits=30)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id

    refused = _refused(
        await send(client, token, woman_id, gift, shown=shown), "PRICE_CHANGED", 409
    )

    assert refused["details"] == {"price": now}
    await _nothing_written(db, man_id, 30, published, woman_id)


async def test_too_few_velas_takes_the_send_back_too(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    await set_config(db, FREE, 0)
    man, token = await make_user(credits=4)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id

    refused = _refused(
        await send(client, token, woman_id, "coffee", shown=5),
        "INSUFFICIENT_CREDITS",
        402,
    )

    assert refused["details"] == {"required": 5, "balance": 4}
    await _nothing_written(db, man_id, 4, published, woman_id)


async def test_a_body_naming_its_own_price_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    """Rule 6: only the shown price, which is compared; never a price to charge."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id = man.id

    _refused(
        await send(client, token, woman.id, credits_charged=0),
        "VALIDATION_ERROR",
        400,
    )
    await _nothing_written(db, man_id, 0, published)


# --- Who sends, to whom, which gift --------------------------------------------------


async def test_a_woman_sending_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    woman, token = await make_user(Gender.FEMALE)
    other, _ = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    woman_id = woman.id

    for recipient in (other.id, man.id):
        _refused(await send(client, token, recipient), "NOT_ALLOWED", 422)

    assert await sends_by(db, woman_id) == []
    assert published == []


async def test_a_man_he_can_reach_is_not_allowed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    """Both seeking everyone, so the reach rule lets him; a gift still goes
    only to a woman."""
    man, token = await make_user()
    other, _ = await make_user()
    man_id, other_id = man.id, other.id
    await db.execute(
        update(Profile)
        .where(Profile.user_id.in_((man_id, other_id)))
        .values(seeking=Seeking.EVERYONE)
    )

    _refused(await send(client, token, other_id), "NOT_ALLOWED", 422)
    await _nothing_written(db, man_id, 0, published, other_id)


@pytest.mark.parametrize("who", ["she blocked him", "he blocked her"])
async def test_a_block_either_way_is_not_found_never_revealed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    who: str,
) -> None:
    """D-653: the same answer as an id nobody holds (D-493)."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    if who == "she blocked him":
        await block(db, woman, man)
    else:
        await block(db, man, woman)

    blocked = _refused(await send(client, token, woman_id), "NOT_FOUND", 404)
    nobody = _refused(await send(client, token, uuid.uuid4()), "NOT_FOUND", 404)

    assert blocked == nobody
    await _nothing_written(db, man_id, 0, published, woman_id)


@pytest.mark.parametrize(
    "state",
    [
        "not done",
        "hidden",
        "paused",
        "frozen by moderation",
        "seeking women",
        "himself",
    ],
)
async def test_someone_he_cant_reach_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    state: str,
) -> None:
    """D-653: whom a private message could reach (D-550), or `NOT_FOUND`; a
    woman who hasn't finished isn't shown to be anyone."""
    man, token = await make_user()
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE, onboarded=state != "not done")
    woman_id = woman.id
    if state == "hidden":
        await db.execute(
            update(Profile).where(Profile.user_id == woman_id).values(is_hidden=True)
        )
    elif state == "paused":
        await db.execute(
            update(User).where(User.id == woman_id).values(status=UserStatus.PAUSED)
        )
    elif state == "frozen by moderation":
        await banded(db, woman, FraudBand.FREEZE)
    elif state == "seeking women":
        await db.execute(
            update(Profile)
            .where(Profile.user_id == woman_id)
            .values(seeking=Seeking.WOMEN)
        )
    recipient = man_id if state == "himself" else woman_id

    _refused(await send(client, token, recipient), "NOT_FOUND", 404)
    await _nothing_written(db, man_id, 0, published, woman_id)


@pytest.mark.parametrize("gift", ["smile", "wave", "diamond"])
async def test_a_gift_not_on_sale_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    gift: str,
) -> None:
    """`smile` and `wave` are retired, never deleted (D-252); `diamond` was
    never a gift."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id

    _refused(await send(client, token, woman_id, gift), "NOT_FOUND", 404)
    await _nothing_written(db, man_id, 0, published, woman_id)


async def test_a_frozen_sender_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    man, token = await make_user(credits=5)
    woman, _ = await make_user(Gender.FEMALE)
    man_id = man.id
    await db.execute(
        update(User).where(User.id == man_id).values(status=UserStatus.FROZEN)
    )

    _refused(await send(client, token, woman.id), "ACCOUNT_FROZEN", 403)
    await _nothing_written(db, man_id, 5, published)


async def test_a_sender_still_onboarding_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    man, token = await make_user(onboarded=False)
    woman, _ = await make_user(Gender.FEMALE)
    man_id = man.id

    _refused(await send(client, token, woman.id), "ONBOARDING_INCOMPLETE", 403)
    await _nothing_written(db, man_id, 0, published)


# --- The cooldown (D-016) --------------------------------------------------------------


async def test_the_same_gift_to_the_same_woman_waits_the_cooldown(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    published: list[events.Event],
) -> None:
    clock.freeze(NOON)
    await set_config(db, COOLDOWN, 3)  # hours, read from the row
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    other, _ = await make_user(Gender.FEMALE)
    man_id, woman_id, other_id = man.id, woman.id, other.id
    await sent(client, token, woman_id, "coffee")
    published.clear()

    refused = _refused(
        await send(client, token, woman_id, "coffee"), "GIFT_COOLDOWN", 429
    )
    assert refused["details"] == {"retry_after_s": 3 * 3600}
    clock.advance(timedelta(hours=2, minutes=59, seconds=59, microseconds=500_000))
    token = token_for(man_id)
    refused = _refused(
        await send(client, token, woman_id, "coffee"), "GIFT_COOLDOWN", 429
    )
    assert refused["details"] == {"retry_after_s": 1}  # rounded up, never 0
    assert published == []
    assert len(await sends_by(db, man_id)) == 1

    # Another gift, or another woman, never waited.
    await sent(client, token, woman_id, "rose")
    await sent(client, token, other_id, "coffee")
    clock.advance(timedelta(microseconds=500_000))  # exactly 3 hours on
    await sent(client, token, woman_id, "coffee")

    assert len(await sends_by(db, man_id)) == 4


async def test_a_paid_send_waits_the_cooldown_too(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
) -> None:
    """D-016: paid gifts have no cap, but respect the cooldown."""
    clock.freeze(NOON)
    await set_config(db, FREE, 0)
    man, token = await make_user(credits=20)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await sent(client, token, woman_id, "coffee", shown=5)

    _refused(
        await send(client, token, woman_id, "coffee", shown=5), "GIFT_COOLDOWN", 429
    )

    assert await balance(db, man_id) == 15
    assert len(await ledger(db, man_id)) == 1


# --- The key (D-653) -------------------------------------------------------------------


async def test_the_same_key_again_is_the_same_send_charged_once(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    await set_config(db, FREE, 0)
    man, token = await make_user(credits=20)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    key = uuid.uuid4().hex

    first = await sent(client, token, woman_id, "rose", shown=10, key=key)
    published.clear()
    # A retry is never refused by its own cooldown, nor by the price shown.
    again = await sent(client, token, woman_id, "rose", shown=10, key=key)

    assert again == first
    assert len(await sends_by(db, man_id)) == 1
    assert await ledger(db, man_id) == [("gift", -10, uuid.UUID(first["id"]))]
    assert await balance(db, man_id) == 10
    assert published == []
    assert len(await notes(db, woman_id)) == 1


@pytest.mark.parametrize("change", ["another gift", "another woman"])
async def test_the_same_key_for_another_send_already_exists(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    change: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    other, _ = await make_user(Gender.FEMALE)
    man_id, woman_id, other_id = man.id, woman.id, other.id
    key = uuid.uuid4().hex
    await sent(client, token, woman_id, "rose", key=key)

    if change == "another gift":
        response = await send(client, token, woman_id, "coffee", key=key)
    else:
        response = await send(client, token, other_id, "rose", key=key)

    _refused(response, "ALREADY_EXISTS", 409)
    assert len(await sends_by(db, man_id)) == 1


async def test_a_key_belongs_to_its_sender(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Two men who happen to send one key each send their own gift."""
    _one, one_token = await make_user()
    _two, two_token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    key = uuid.uuid4().hex

    a = await sent(client, one_token, woman.id, "rose", key=key)
    b = await sent(client, two_token, woman.id, "rose", key=key)

    assert a["id"] != b["id"]


@pytest.mark.parametrize("key", [None, "short", "has space in it", "x" * 65])
async def test_a_send_needs_a_key_of_the_right_shape(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
    key: str | None,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id = man.id
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key

    response = await client.post(
        "/v1/gifts/send",
        json={"recipient_id": str(woman.id), "gift_id": "rose"},
        headers=headers,
    )

    _refused(response, "VALIDATION_ERROR", 400)
    await _nothing_written(db, man_id, 0, published)


# --- The Thread ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "linked"),
    [
        ("active", True),
        ("knotted", True),
        ("expired", False),
        ("expired by the clock", False),
        ("none", False),
    ],
)
async def test_a_live_thread_is_linked_and_none_is_ever_opened(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    clock: ModuleType,
    state: str,
    linked: bool,
) -> None:
    clock.freeze(NOON)
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    thread_id = None
    if state != "none":
        status = "active" if state == "expired by the clock" else state
        thread = await make_thread(man, woman, status=ThreadStatus(status))
        thread_id = thread.id
        if state == "expired by the clock":
            # Its status not yet caught up by the cron (D-560).
            clock.advance(timedelta(hours=25))
            token = token_for(man_id)

    body = await sent(client, token, woman_id, "rose")

    assert body["thread_id"] == (str(thread_id) if linked else None)
    low, high = sorted((man_id, woman_id))
    threads = await db.scalar(
        select(func.count())
        .select_from(Thread)
        .where(Thread.user_low == low, Thread.user_high == high)
    )
    assert threads == (0 if state == "none" else 1)


# --- The limit ----------------------------------------------------------------------


async def test_sends_are_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    for _ in range(SENDS_PER_MINUTE):
        _refused(await send(client, token, uuid.uuid4()), "NOT_FOUND", 404)

    _refused(await send(client, token, uuid.uuid4()), "RATE_LIMITED", 429)
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == man.id)
    )
    assert count == 0
