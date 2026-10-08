"""`POST /v1/kudos` (T-8.5, D-007, D-680): one of four fixed kinds, once ever
to each person, only to someone you have talked with: the pair's Thread has
`kudos_min_messages` messages (6 as seeded) and each has written one. No
Thread, a block, an unknown id or yourself are one `NOT_FOUND`; a deleted
account gets nothing more."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.core.enums import Gender, MessageKind, UserStatus
from app.modules.kudos.models import Kudos
from app.modules.kudos.router import GIVES_PER_MINUTE
from app.modules.messages.models import Message
from app.modules.safety.models import Block
from app.modules.threads.models import Thread
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, error

pytestmark = pytest.mark.usefixtures("test_redis")


async def _give(
    client: AsyncClient, token: str, to_id: uuid.UUID, kind: str = "great_conversation"
) -> Response:
    return await client.post(
        "/v1/kudos", json={"to_id": str(to_id), "kind": kind}, headers=bearer(token)
    )


async def _talked(
    db: AsyncSession,
    make_thread: MakeThread,
    a: User,
    b: User,
    *,
    mine: int = 5,
    theirs: int = 1,
    status: str = "active",
) -> Thread:
    """A Thread opened by `a`, with `mine` messages from `a` and `theirs` from
    `b`, all counted."""
    thread = await make_thread(a, b, status=status, messages=mine)
    for n in range(theirs):
        db.add(
            Message(
                thread_id=thread.id,
                sender_id=b.id,
                kind=MessageKind.TEXT,
                body=f"Reply {n + 1}",
                client_msg_id=uuid.uuid4(),
            )
        )
    thread.message_count = mine + theirs
    await db.flush()
    return thread


async def _given(db: AsyncSession, from_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    rows = await db.execute(
        select(Kudos.to_id, Kudos.kind).where(Kudos.from_id == from_id)
    )
    return [(to_id, str(kind)) for to_id, kind in rows]


async def _config(db: AsyncSession, key: str, value: int) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
        {"k": key, "v": str(value)},
    )


# --- Given ---------------------------------------------------------------------------


async def test_kudos_is_given_once_to_them_in_their_thread(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await _talked(db, make_thread, man, woman)

    response = await _give(client, token, woman.id, "genuinely_funny")

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"to_id", "kind", "created_at"}
    assert (body["to_id"], body["kind"]) == (str(woman.id), "genuinely_funny")
    row = await db.scalar(select(Kudos).where(Kudos.from_id == man.id))
    assert row is not None
    assert (row.to_id, row.kind, row.thread_id) == (
        woman.id,
        "genuinely_funny",
        thread.id,
    )


@pytest.mark.parametrize(
    "kind",
    ["great_conversation", "genuinely_funny", "easy_to_talk_to", "really_thoughtful"],
)
async def test_each_of_the_four_kinds_can_be_given(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    kind: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _talked(db, make_thread, man, woman)

    assert (await _give(client, token, woman.id, kind)).status_code == 201
    assert await _given(db, man.id) == [(woman.id, kind)]


@pytest.mark.parametrize("status", ["expired", "knotted"])
async def test_a_thread_that_ended_or_was_knotted_still_counts(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    status: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _talked(db, make_thread, man, woman, status=status)

    assert (await _give(client, token, woman.id)).status_code == 201


async def test_either_of_the_two_can_give_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his = await make_user()
    woman, hers = await make_user(Gender.FEMALE)
    await _talked(db, make_thread, man, woman)

    assert (await _give(client, his, woman.id)).status_code == 201
    assert (await _give(client, hers, man.id, "easy_to_talk_to")).status_code == 201
    assert await _given(db, woman.id) == [(man.id, "easy_to_talk_to")]


# --- Once ever -------------------------------------------------------------------------


@pytest.mark.parametrize("second", ["great_conversation", "really_thoughtful"])
async def test_a_second_kudos_to_them_already_exists(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    second: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await _talked(db, make_thread, man, woman)
    assert (await _give(client, token, woman_id)).status_code == 201

    response = await _give(client, token, woman_id, second)

    assert response.status_code == 409
    assert error(response)["code"] == "ALREADY_EXISTS"
    assert await _given(db, man_id) == [(woman_id, "great_conversation")]


# --- Talked with (D-680) ------------------------------------------------------------------


async def test_six_messages_are_enough_and_five_too_few(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    early, _ = await make_user(Gender.FEMALE)
    ready, _ = await make_user(Gender.FEMALE)
    man_id, early_id, ready_id = man.id, early.id, ready.id
    await _talked(db, make_thread, man, early, mine=4, theirs=1)
    await _talked(db, make_thread, man, ready, mine=5, theirs=1)

    refused = await _give(client, token, early_id)

    assert refused.status_code == 422
    assert error(refused)["code"] == "NOT_ALLOWED"
    assert error(refused)["details"] == {"why": "too_early"}
    assert (await _give(client, token, ready_id)).status_code == 201
    assert await _given(db, man_id) == [(ready_id, "great_conversation")]


async def test_the_least_is_read_from_app_config(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    await _config(db, "kudos_min_messages", 3)
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _talked(db, make_thread, man, woman, mine=2, theirs=1)

    assert (await _give(client, token, woman.id)).status_code == 201


async def test_a_one_sided_thread_is_too_early_for_either(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, his = await make_user()
    woman, hers = await make_user(Gender.FEMALE)
    ids = (man.id, woman.id)
    await _talked(db, make_thread, man, woman, mine=8, theirs=0)

    for token, to_id in ((his, ids[1]), (hers, ids[0])):
        refused = await _give(client, token, to_id)
        assert refused.status_code == 422
        assert error(refused)["details"] == {"why": "too_early"}
    received = select(func.count()).select_from(Kudos).where(Kudos.to_id.in_(ids))
    assert await db.scalar(received) == 0


# --- Refused ---------------------------------------------------------------------------


async def _not_found(response: Response) -> None:
    assert response.status_code == 404, response.text
    assert error(response)["code"] == "NOT_FOUND"


async def test_no_thread_an_unknown_id_or_yourself_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    stranger, _ = await make_user(Gender.FEMALE)
    man_id = man.id

    for to_id in (stranger.id, uuid.uuid4(), man_id):
        await _not_found(await _give(client, token, to_id))
    assert await _given(db, man_id) == []


@pytest.mark.parametrize("who_blocked", ["giver", "recipient"])
async def test_a_block_either_way_is_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    who_blocked: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _talked(db, make_thread, man, woman)
    blocker, blocked = (man, woman) if who_blocked == "giver" else (woman, man)
    db.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    await db.flush()
    man_id = man.id

    await _not_found(await _give(client, token, woman.id))
    assert await _given(db, man_id) == []


async def test_nothing_reaches_a_deleted_account(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _talked(db, make_thread, man, woman)
    await db.execute(
        update(User)
        .where(User.id == woman.id)
        .values(
            status=UserStatus.DELETED,
            deleted_requested_at=clock_now() - timedelta(minutes=1),
        )
    )

    man_id = man.id

    response = await _give(client, token, woman.id)

    assert response.status_code == 410
    assert error(response)["code"] == "ACCOUNT_DELETED"
    assert await _given(db, man_id) == []


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "creepy"},
        {"kind": "Great conversation"},
        {"kind": None},
        {"note": "You were lovely"},
    ],
)
async def test_only_the_four_fixed_kinds_and_nothing_else(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    body: dict[str, object],
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id = man.id
    await _talked(db, make_thread, man, woman)

    response = await client.post(
        "/v1/kudos",
        json={"to_id": str(woman.id), "kind": "great_conversation", **body},
        headers=bearer(token),
    )

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await _given(db, man_id) == []


async def test_giving_needs_onboarding_done(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await _give(client, token, uuid.uuid4())

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


@pytest.mark.usefixtures("db")
async def test_giving_needs_a_sign_in(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/kudos", json={"to_id": str(uuid.uuid4()), "kind": "great_conversation"}
    )

    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


async def test_giving_is_rate_limited_at_ten_a_minute(
    client: AsyncClient, make_user: MakeUser
) -> None:
    assert GIVES_PER_MINUTE == 10
    _, token = await make_user()
    for _ in range(10):
        await _not_found(await _give(client, token, uuid.uuid4()))

    response = await _give(client, token, uuid.uuid4())

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"
