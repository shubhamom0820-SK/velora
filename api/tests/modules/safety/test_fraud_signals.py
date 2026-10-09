"""T-9.2's signals, each written by the service that sees it (D-900): a report
received, a contact detail masked, more than 30 Threads opened in a day, the
same first message to more than 10 people, more than 3 sign-ins in 7 days
(D-903), and a move of more than 500 km within an hour. Each at its threshold
and not one below; a threshold signal once a day; none carries a message, a
place or a number."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core.enums import Gender, MessageKind
from app.core.providers import FakeProviders
from app.modules.messages.models import Message
from app.modules.safety.models import FraudEvent
from tests.conftest import MakeThread, MakeUser
from tests.modules.auth.test_refresh import Device
from tests.modules.discovery.support import bearer, north
from tests.modules.safety.support import report
from tests.modules.threads.test_open import _match, _opened

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 9, 6, 30, tzinfo=UTC)


async def signals(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int, Any]]:
    rows = await db.execute(
        select(FraudEvent.signal, FraudEvent.weight, FraudEvent.meta)
        .where(FraudEvent.user_id == user_id)
        .order_by(FraudEvent.created_at, FraudEvent.signal)
        .execution_options(populate_existing=True)
    )
    return [(row[0], row[1], row[2]) for row in rows]


# --- A report ------------------------------------------------------------------------


async def test_a_report_is_a_signal_on_the_person_reported_naming_the_report(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    me_id, him_id = me.id, him.id

    response = await report(client, token, him_id, reason="scam")

    assert response.status_code == 201, response.text
    report_id = response.json()["id"]
    assert await signals(db, him_id) == [
        ("report_received", 20, {"report_id": report_id, "reason": "scam"})
    ]
    assert await signals(db, me_id) == []


# --- A contact detail masked -----------------------------------------------------------


async def test_a_masked_contact_is_a_signal_and_never_the_message(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=20)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    plain, _ = await make_user(Gender.FEMALE)

    await _opened(
        client, token, user_id=woman.id, shown_price=8, first_message="call 9876543210"
    )
    assert await signals(db, man_id) == [("contact_masked", 2, None)]

    await _opened(client, token, user_id=plain.id, shown_price=8, first_message="Hi")
    assert await signals(db, man_id) == [("contact_masked", 2, None)]


# --- More than 30 Threads opened in a day ----------------------------------------------


async def _opened_directly(
    db: AsyncSession, make_user: MakeUser, make_thread: MakeThread, him: Any, n: int
) -> None:
    for _ in range(n):
        other, _ = await make_user(Gender.FEMALE)
        await make_thread(him, other)


@pytest.mark.parametrize(("before", "signalled"), [(29, False), (30, True)])
async def test_more_than_30_threads_opened_in_a_day_is_a_signal(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    before: int,
    signalled: bool,
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    await _opened_directly(db, make_user, make_thread, man, before)
    # One she opened doesn't count: it's his he opened.
    her, _ = await make_user(Gender.FEMALE)
    await make_thread(her, man)
    woman, _ = await make_user(Gender.FEMALE)
    match = await _match(db, man, woman)

    await _opened(client, token, match_id=match.id, shown_price=5)

    expected = [("many_new_threads", 25, {"threads": before + 1})] if signalled else []
    assert await signals(db, man_id) == expected


async def test_a_threshold_signal_is_written_once_a_day(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    await _opened_directly(db, make_user, make_thread, man, 30)
    for _ in range(2):
        woman, _ = await make_user(Gender.FEMALE)
        match = await _match(db, man, woman)
        await _opened(client, token, match_id=match.id, shown_price=5)

    assert await signals(db, man_id) == [("many_new_threads", 25, {"threads": 31})]


# --- The same first message to more than 10 people ---------------------------------------


async def _first_messages(
    db: AsyncSession,
    make_user: MakeUser,
    make_thread: MakeThread,
    him: Any,
    text: str,
    n: int,
) -> None:
    for _ in range(n):
        other, _ = await make_user(Gender.FEMALE)
        thread = await make_thread(him, other)
        db.add(
            Message(
                thread_id=thread.id,
                sender_id=him.id,
                kind=MessageKind.TEXT,
                body=text,
                client_msg_id=uuid.uuid4(),
            )
        )
        thread.message_count = 1
    await db.flush()


@pytest.mark.parametrize(("before", "signalled"), [(9, False), (10, True)])
async def test_the_same_first_message_to_more_than_10_people_is_a_signal(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    before: int,
    signalled: bool,
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    await _first_messages(db, make_user, make_thread, man, "Hey, how are you?", before)
    # Not a first message: the Thread's first was hers.
    her, _ = await make_user(Gender.FEMALE)
    theirs = await make_thread(her, man, messages=1)
    db.add(
        Message(
            thread_id=theirs.id,
            sender_id=man.id,
            kind=MessageKind.TEXT,
            body="Hey, how are you?",
            client_msg_id=uuid.uuid4(),
            created_at=core_clock.now() + timedelta(seconds=5),
        )
    )
    woman, _ = await make_user(Gender.FEMALE)

    # Case and spacing ignored.
    await _opened(
        client,
        token,
        user_id=woman.id,
        shown_price=8,
        first_message="  hey,   HOW are you?",
    )

    expected = (
        [("identical_first_message", 25, {"people": before + 1})] if signalled else []
    )
    assert await signals(db, man_id) == expected


async def test_different_first_messages_are_no_signal(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    await _first_messages(db, make_user, make_thread, man, "Hey, how are you?", 10)
    woman, _ = await make_user(Gender.FEMALE)

    await _opened(
        client, token, user_id=woman.id, shown_price=8, first_message="Hey, how are you"
    )

    assert await signals(db, man_id) == []


async def test_the_first_message_of_a_thread_from_a_match_counts_too(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user(credits=10)
    man_id = man.id
    await _first_messages(db, make_user, make_thread, man, "Namaste", 10)
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)

    response = await client.post(
        f"/v1/threads/{thread.id}/messages",
        json={"kind": "text", "body": "namaste", "client_msg_id": str(uuid.uuid4())},
        headers=bearer(token),
    )

    assert response.status_code in (200, 201), response.text
    assert await signals(db, man_id) == [
        ("identical_first_message", 25, {"people": 11})
    ]


# --- More than 3 sign-ins in 7 days (D-903) ----------------------------------------------


async def _sign_in(
    client: AsyncClient, fake_providers: FakeProviders, clock: ModuleType, phone: str
) -> Device:
    clock.advance(timedelta(seconds=46))
    response = await client.post("/v1/auth/otp/send", json={"phone": phone})
    assert response.status_code == 200, response.text
    code = fake_providers.sms.sent[-1].code
    response = await client.post(
        "/v1/auth/otp/verify", json={"phone": phone, "otp": code}
    )
    assert response.status_code == 200, response.text
    return Device(response)


async def _user_on(db: AsyncSession, phone: str) -> uuid.UUID:
    from app.core.security import E164, hash_phone
    from app.modules.users.models import User
    from tests.conftest import make_test_settings

    found = await db.scalar(
        select(User.id).where(
            User.phone_hash == hash_phone(E164(phone), make_test_settings())
        )
    )
    assert found is not None
    return found


async def test_more_than_three_sign_ins_in_seven_days_is_a_signal(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    phone = "+919900000417"
    for _ in range(3):
        await _sign_in(client, fake_providers, clock, phone)
    user_id = await _user_on(db, phone)
    assert await signals(db, user_id) == []

    await _sign_in(client, fake_providers, clock, phone)

    assert await signals(db, user_id) == [("many_sign_ins", 15, {"sign_ins": 4})]


async def test_sign_ins_older_than_seven_days_dont_count(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    phone = "+919900000418"
    for _ in range(3):
        await _sign_in(client, fake_providers, clock, phone)
    clock.advance(timedelta(days=7, minutes=1))

    await _sign_in(client, fake_providers, clock, phone)

    assert await signals(db, await _user_on(db, phone)) == []


async def test_refreshing_a_session_is_no_sign_in(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """A rotation keeps its family: only a sign-in starts one. Four refreshes
    and a second sign-in are two sign-ins, counted at the second."""
    clock.freeze(START)
    phone = "+919900000419"
    device = await _sign_in(client, fake_providers, clock, phone)
    for _ in range(4):
        clock.advance(timedelta(minutes=1))
        response = await client.post("/v1/auth/refresh", headers=device.headers())
        assert response.status_code == 200, response.text
        device.take(response)

    await _sign_in(client, fake_providers, clock, phone)

    assert await signals(db, await _user_on(db, phone)) == []


async def test_an_under_18_refusal_takes_a_signal_written_before_the_dob(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """D-078 (P-54): sign-ins come before the dob step, so their signal can
    exist when a date of birth is refused, and goes with everything else."""
    clock.freeze(START)
    phone = "+919900000420"
    for _ in range(4):
        await _sign_in(client, fake_providers, clock, phone)
    user_id = await _user_on(db, phone)
    assert [signal for signal, _, _ in await signals(db, user_id)] == ["many_sign_ins"]
    clock.advance(timedelta(seconds=46))
    await client.post("/v1/auth/otp/send", json={"phone": phone})
    signed_in = await client.post(
        "/v1/auth/otp/verify",
        json={"phone": phone, "otp": fake_providers.sms.sent[-1].code},
    )
    token = signed_in.json()["access_token"]

    refused = await client.post(
        "/v1/me/dob", json={"dob": "2015-01-01"}, headers=bearer(token)
    )

    assert refused.json()["error"]["code"] == "UNDERAGE"
    assert await signals(db, user_id) == []


# --- A location jump ---------------------------------------------------------------------

PHAGWARA = (31.22, 75.77)
CHENNAI = (13.08, 80.27)


async def _move(client: AsyncClient, token: str, at: tuple[float, float]) -> None:
    response = await client.put(
        "/v1/me/location", json={"lat": at[0], "lng": at[1]}, headers=bearer(token)
    )
    assert response.status_code == 200, response.text


async def _located_ago(db: AsyncSession, user_id: uuid.UUID, ago: timedelta) -> None:
    """The last location written `ago`: tokens last 15 minutes, so the clock
    isn't moved an hour."""
    from app.core import clock as core_clock
    from app.modules.profiles.models import Profile

    profile = await db.get(Profile, user_id, populate_existing=True)
    assert profile is not None
    profile.location_updated_at = core_clock.now() - ago
    await db.flush()


async def test_more_than_500_km_within_an_hour_is_a_signal_of_its_distance_only(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    me_id = me.id
    await _move(client, token, PHAGWARA)
    await _located_ago(db, me_id, timedelta(minutes=59))

    await _move(client, token, CHENNAI)

    [(signal, weight, meta)] = await signals(db, me_id)
    assert (signal, weight) == ("location_jump", 15)
    assert set(meta) == {"km"}
    assert 2000 < meta["km"] < 2100


async def test_a_far_move_after_an_hour_or_a_near_one_is_no_signal(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    me_id = me.id
    await _move(client, token, PHAGWARA)
    await _move(client, token, north(3))  # 3 km from Phagwara
    await _located_ago(db, me_id, timedelta(hours=1, minutes=1))

    await _move(client, token, CHENNAI)

    assert await signals(db, me_id) == []


async def test_the_first_location_is_no_jump(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    me_id = me.id
    await _move(client, token, CHENNAI)
    assert await signals(db, me_id) == []
