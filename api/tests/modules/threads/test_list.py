"""`GET /v1/threads` and `GET /v1/threads/{id}` (T-7.2): my Threads or my
Knots, newest first; cleared ones hidden for me alone until something newer
comes (D-006); a block hides a Thread both ways; a deleted account's row says
so and nothing more (D-051, D-500); the unread count, the preview, the
filters and the search; her rows carry no expiry (D-554)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, MessageKind, UserStatus
from app.modules.messages.models import Message
from app.modules.profiles.models import Profile
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")


async def _list(client: AsyncClient, token: str, **query: Any) -> Response:
    return await client.get("/v1/threads", params=query, headers=bearer(token))


async def _rows(client: AsyncClient, token: str, **query: Any) -> list[dict[str, Any]]:
    response = await _list(client, token, **query)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body["next_cursor"] is None
    rows: list[dict[str, Any]] = body["items"]
    return rows


async def _say(
    db: AsyncSession,
    thread: Thread,
    sender: User,
    body: str | None = "Hello",
    *,
    ago: timedelta = timedelta(0),
    kind: MessageKind = MessageKind.TEXT,
    read: bool = False,
) -> Message:
    """A message `ago` before now, the Thread's last if it is the newest."""
    at = clock.now() - ago
    message = Message(
        thread_id=thread.id,
        sender_id=sender.id,
        kind=kind,
        body=body,
        client_msg_id=uuid.uuid4(),
        created_at=at,
        read_at=at if read else None,
    )
    db.add(message)
    thread.message_count += 1
    if thread.last_message_at is None or at > thread.last_message_at:
        thread.last_message_at = at
    await db.flush()
    return message


async def _named(db: AsyncSession, user: User, first_name: str, username: str) -> None:
    await db.execute(
        update(Profile)
        .where(Profile.user_id == user.id)
        .values(first_name=first_name, username=username)
    )


# --- The rows ---------------------------------------------------------------------


async def test_my_threads_newest_first_with_their_preview_and_unread(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    older, _ = await make_user(Gender.FEMALE)
    newer, _ = await make_user(Gender.FEMALE)
    strangers = (await make_user())[0], (await make_user(Gender.FEMALE))[0]
    first = await make_thread(man, older)
    second = await make_thread(man, newer)
    await make_thread(*strangers)
    await _say(db, first, older, "From her, earlier", ago=timedelta(hours=2))
    # Mine, unread by her: never in my unread count.
    await _say(db, second, man, "Mine", ago=timedelta(hours=1))
    await _say(db, second, newer, "x" * 150, ago=timedelta(minutes=5))
    await _say(db, second, newer, "Read already", ago=timedelta(minutes=1), read=True)

    rows = await _rows(client, token)

    assert [row["id"] for row in rows] == [str(second.id), str(first.id)]
    top = rows[0]
    assert set(top) == {
        "id",
        "origin",
        "status",
        "expires_at",
        "knotted_at",
        "i_tied",
        "unread",
        "last_message",
        "last_message_at",
        "other",
    }
    assert top["unread"] == 1
    assert top["last_message"]["text"] == "Read already"
    assert top["last_message"]["mine"] is False
    assert top["status"] == "active" and top["i_tied"] is False
    assert top["expires_at"] is not None  # a man sees it
    assert top["other"] == {
        "id": str(newer.id),
        "first_name": "Test",
        "username": top["other"]["username"],
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": False,
    }
    assert top["other"]["username"].startswith("user")
    assert rows[1]["unread"] == 1


async def test_a_preview_is_a_texts_first_hundred_characters(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, "y" * 150)

    [row] = await _rows(client, token)

    assert row["last_message"]["text"] == "y" * 100


async def test_a_voice_notes_preview_has_no_text(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """The web names it ("Voice note"), so no copy lives in the API."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, None, kind=MessageKind.VOICE)

    [row] = await _rows(client, token)

    assert row["last_message"]["kind"] == "voice"
    assert row["last_message"]["text"] is None


async def test_a_thread_with_no_message_yet_sorts_by_its_opening(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await make_thread(man, woman)

    [row] = await _rows(client, token)

    assert row["last_message"] is None and row["unread"] == 0


async def test_her_row_carries_no_expiry(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, token = await make_user(Gender.FEMALE)
    await make_thread(man, woman)

    [row] = await _rows(client, token)

    assert row["expires_at"] is None


# --- Tiers, filters, search -------------------------------------------------------


async def test_threads_and_knots_are_separate_tiers(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    women = [(await make_user(Gender.FEMALE))[0] for _ in range(3)]
    active = await make_thread(man, women[0])
    expired = await make_thread(man, women[1], status="expired")
    knot = await make_thread(man, women[2], status="knotted")

    threads = await _rows(client, token)
    knots = await _rows(client, token, tier="knots")

    assert {row["id"] for row in threads} == {str(active.id), str(expired.id)}
    assert [row["id"] for row in knots] == [str(knot.id)]
    assert knots[0]["i_tied"] is True


async def test_unread_keeps_those_with_something_unread(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    waiting = await make_thread(man, one, status="knotted")
    caught_up = await make_thread(man, two, status="knotted")
    await _say(db, waiting, one)
    await _say(db, caught_up, two, read=True)
    await _say(db, caught_up, man)

    rows = await _rows(client, token, tier="knots", filter="unread")

    assert [row["id"] for row in rows] == [str(waiting.id)]


async def test_recent_is_a_message_in_the_last_three_days(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    recent = await make_thread(man, one, status="knotted")
    quiet = await make_thread(man, two, status="knotted")
    await _say(db, recent, one, ago=timedelta(days=2, hours=23))
    await _say(db, quiet, two, ago=timedelta(days=3, minutes=1))

    rows = await _rows(client, token, tier="knots", filter="recent")

    assert [row["id"] for row in rows] == [str(recent.id)]


async def test_q_finds_their_name_or_username_anywhere_in_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    priya, _ = await make_user(Gender.FEMALE)
    meera, _ = await make_user(Gender.FEMALE)
    await _named(db, priya, "Priya", "sunny_days")
    await _named(db, meera, "Meera", "pri_ya100")
    by_priya = await make_thread(man, priya)
    by_meera = await make_thread(man, meera)

    by_name = await _rows(client, token, q="RIY")
    by_username = await _rows(client, token, q="sunny")
    literal = await _rows(client, token, q="pri_")
    wildcard = await _rows(client, token, q="%")

    assert [row["id"] for row in by_name] == [str(by_priya.id)]
    assert [row["id"] for row in by_username] == [str(by_priya.id)]
    # `_` is a letter here, never ILIKE's any-character.
    assert [row["id"] for row in literal] == [str(by_meera.id)]
    assert wildcard == []


# --- Hidden: clearing, blocks -------------------------------------------------------


async def test_a_cleared_thread_hides_for_me_alone_until_something_newer(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    # Unread, and before the clearing: never counted once cleared.
    await _say(db, thread, woman, "Before", ago=timedelta(hours=2))
    db.add(
        ThreadClear(
            user_id=man.id,
            thread_id=thread.id,
            cleared_at=clock.now() - timedelta(hours=1),
        )
    )
    await db.flush()

    hidden = await _rows(client, token)
    hers = await _rows(client, her_token)
    await _say(db, thread, woman, "After")
    back = await _rows(client, token)

    assert hidden == []
    assert [row["id"] for row in hers] == [str(thread.id)]
    assert [row["id"] for row in back] == [str(thread.id)]
    # Only what came after the clearing counts as unread.
    assert back[0]["unread"] == 1


@pytest.mark.critical
async def test_each_thread_counts_its_unread_after_its_own_clearing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """Found building T-9.8: the unread count's clearing took every clearing
    the viewer had, not its own Thread's, so two clearings and one unread
    message made the chats list a 500. Each Thread's count reads its own."""
    man, token = await make_user()
    one, _ = await make_user(Gender.FEMALE)
    two, _ = await make_user(Gender.FEMALE)
    first = await make_thread(man, one)
    second = await make_thread(man, two)
    await _say(db, first, one, "Before", ago=timedelta(hours=3))
    await _say(db, second, two, "Before", ago=timedelta(hours=3))
    for thread, hours in ((first, 2), (second, 1)):
        db.add(
            ThreadClear(
                user_id=man.id,
                thread_id=thread.id,
                cleared_at=clock.now() - timedelta(hours=hours),
            )
        )
    await db.flush()
    await _say(db, first, one, "After")
    await _say(db, first, one, "And again")
    await _say(db, second, two, "After")

    rows = {row["id"]: row["unread"] for row in await _rows(client, token)}

    assert rows == {str(first.id): 2, str(second.id): 1}


@pytest.mark.parametrize("who_blocks", ["me", "them"])
async def test_a_block_either_way_hides_the_thread(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    who_blocks: str,
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    if who_blocks == "me":
        await block(db, man, woman)
    else:
        await block(db, woman, man)
    thread_id = thread.id

    mine = await _rows(client, token)
    hers = await _rows(client, her_token)
    one = await client.get(f"/v1/threads/{thread_id}", headers=bearer(token))

    assert mine == [] and hers == []
    assert one.status_code == 404
    assert error(one)["code"] == "NOT_FOUND"


# --- A deleted account (D-051, D-500) ----------------------------------------------


async def test_a_deleted_account_is_named_as_one_and_nothing_more(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await _named(db, woman, "Priya", "priya_k")
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, "Still here")
    await db.execute(
        update(User)
        .where(User.id == woman.id)
        .values(
            status=UserStatus.DELETED,
            deleted_requested_at=clock.now(),
            last_active_at=clock.now(),
        )
    )

    [row] = await _rows(client, token)
    searched = await _rows(client, token, q="Priya")

    assert row["other"] == {
        "id": str(woman.id),
        "first_name": None,
        "username": None,
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": True,
    }
    # The Thread stays, as the messages do.
    assert row["last_message"]["text"] == "Still here"
    assert searched == []


# --- Pages and refusals -----------------------------------------------------------


async def test_pages_follow_the_cursor(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    threads = []
    for hours in (3, 2, 1):
        woman, _ = await make_user(Gender.FEMALE)
        thread = await make_thread(man, woman)
        await _say(db, thread, woman, ago=timedelta(hours=hours))
        threads.append(thread)

    first = await _list(client, token, limit=2)
    cursor = first.json()["next_cursor"]
    second = await _list(client, token, limit=2, cursor=cursor)

    assert [row["id"] for row in first.json()["items"]] == [
        str(threads[2].id),
        str(threads[1].id),
    ]
    assert cursor is not None
    assert [row["id"] for row in second.json()["items"]] == [str(threads[0].id)]
    assert second.json()["next_cursor"] is None


@pytest.mark.parametrize(
    "query",
    [
        {"tier": "all"},
        {"filter": "starred"},
        {"limit": 0},
        {"limit": 51},
        {"cursor": "not-a-cursor"},
        {"q": ""},
        {"q": "x" * 51},
    ],
)
async def test_a_bad_query_is_a_validation_error(
    client: AsyncClient, make_user: MakeUser, query: dict[str, Any]
) -> None:
    _, token = await make_user()

    response = await _list(client, token, **query)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_one_thread_is_mine_to_read_and_nobody_elses(
    client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    _, stranger_token = await make_user()
    url = f"/v1/threads/{(await make_thread(man, woman)).id}"
    woman_id = woman.id

    mine = await client.get(url, headers=bearer(token))
    hers = await client.get(url, headers=bearer(her_token))
    theirs = await client.get(url, headers=bearer(stranger_token))
    nobody = await client.get(f"/v1/threads/{uuid.uuid4()}", headers=bearer(token))

    assert mine.status_code == 200
    assert mine.json()["other_user_id"] == str(woman_id)
    assert mine.json()["expires_at"] is not None
    assert hers.json()["expires_at"] is None
    assert theirs.status_code == 404 and nobody.status_code == 404


async def test_onboarding_comes_first(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user(onboarded=False)

    response = await _list(client, token)

    assert response.status_code == 403
    assert error(response)["code"] == "ONBOARDING_INCOMPLETE"
