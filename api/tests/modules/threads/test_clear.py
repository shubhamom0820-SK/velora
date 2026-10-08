"""`POST /v1/threads/{id}/clear`, `POST /v1/threads/clear` and `DELETE
/v1/threads/{id}/clear` (T-7.8): clearing hides a Thread from my chats alone
(D-006). The other person's side, the messages and the Thread are exactly as
they were, and moderation still reads every message; a message after the
clearing brings the Thread back with only what is new; `cleared_at` is the
newest message's time, never the tap's (D-610); restoring brings the whole
history back (D-611)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.enums import Gender, MessageKind
from app.modules.messages import repository as messages_repository
from app.modules.messages.models import Message
from app.modules.threads.models import Thread, ThreadClear
from app.modules.threads.router import CLEARS_PER_MINUTE
from app.modules.threads.schemas import CLEAR_MAX
from app.modules.users.models import User
from tests.conftest import MakeThread, MakeUser
from tests.modules.discovery.support import bearer, block, error

pytestmark = pytest.mark.usefixtures("test_redis")


async def _say(
    db: AsyncSession,
    thread: Thread,
    sender: User,
    body: str = "Hello",
    *,
    ago: timedelta = timedelta(0),
) -> Message:
    """A message `ago` before now, unread, the Thread's last if newest."""
    at = clock.now() - ago
    message = Message(
        thread_id=thread.id,
        sender_id=sender.id,
        kind=MessageKind.TEXT,
        body=body,
        body_raw=f"raw {body}",
        client_msg_id=uuid.uuid4(),
        created_at=at,
    )
    db.add(message)
    thread.message_count += 1
    if thread.last_message_at is None or at > thread.last_message_at:
        thread.last_message_at = at
    await db.flush()
    return message


async def _clear(client: AsyncClient, token: str, thread_id: uuid.UUID) -> Response:
    return await client.post(f"/v1/threads/{thread_id}/clear", headers=bearer(token))


async def _restore(client: AsyncClient, token: str, thread_id: uuid.UUID) -> Response:
    return await client.delete(f"/v1/threads/{thread_id}/clear", headers=bearer(token))


async def _clear_many(client: AsyncClient, token: str, body: Any) -> Response:
    return await client.post("/v1/threads/clear", json=body, headers=bearer(token))


async def _list_ids(client: AsyncClient, token: str) -> list[str]:
    response = await client.get("/v1/threads", headers=bearer(token))
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


async def _bodies(client: AsyncClient, token: str, thread_id: uuid.UUID) -> list[str]:
    response = await client.get(
        f"/v1/threads/{thread_id}/messages", headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    return [item["body"] for item in response.json()["items"]]


async def _side(
    client: AsyncClient, token: str, thread_id: uuid.UUID
) -> tuple[Any, Any, Any]:
    """Everything one person's side shows of a Thread: their list, the Thread
    and its messages."""
    rows = await client.get("/v1/threads", headers=bearer(token))
    one = await client.get(f"/v1/threads/{thread_id}", headers=bearer(token))
    page = await client.get(f"/v1/threads/{thread_id}/messages", headers=bearer(token))
    assert rows.status_code == one.status_code == page.status_code == 200
    return rows.json(), one.json(), page.json()


async def _stored(db: AsyncSession, thread_id: uuid.UUID) -> tuple[Any, Any]:
    """The Thread's row and every message's, whole, as the database holds them."""
    thread = await db.scalar(
        text("SELECT to_jsonb(t) FROM threads t WHERE t.id = :t"), {"t": thread_id}
    )
    messages = (
        await db.scalars(
            text(
                "SELECT to_jsonb(m) FROM messages m WHERE m.thread_id = :t ORDER BY m.id"
            ),
            {"t": thread_id},
        )
    ).all()
    return thread, messages


async def _cleared_for(db: AsyncSession, thread_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        await db.scalars(
            select(ThreadClear.user_id).where(ThreadClear.thread_id == thread_id)
        )
    )


async def _notifications(db: AsyncSession, user_id: uuid.UUID) -> int:
    count = await db.scalar(
        text("SELECT count(*) FROM notifications WHERE user_id = :u"), {"u": user_id}
    )
    assert count is not None
    return int(count)


# --- One side alone (D-006) ---------------------------------------------------------


async def test_after_he_clears_she_sees_everything_and_nothing_is_touched(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    published: list[events.Event],
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, "Hi", ago=timedelta(hours=2))
    await _say(db, thread, man, "Hello you", ago=timedelta(hours=1))
    await _say(db, thread, woman, "Unread by him", ago=timedelta(minutes=30))
    man_id, woman_id, thread_id = man.id, woman.id, thread.id
    # His request marks him online (once a minute): presence, not clearing, so
    # it is marked before her side is read.
    assert await _list_ids(client, token) == [str(thread_id)]
    her_side = await _side(client, her_token, thread_id)
    stored = await _stored(db, thread_id)
    her_notifications = await _notifications(db, woman_id)
    before = len(published)

    response = await _clear(client, token, thread_id)

    assert response.status_code == 204, response.text
    assert response.content == b""
    # Hidden for him: gone from his list, his messages page empty.
    assert await _list_ids(client, token) == []
    assert await _bodies(client, token, thread_id) == []
    # Her side, to the byte: the list, the unread count, the Thread, every
    # message and its "Read" (read_at).
    assert await _side(client, her_token, thread_id) == her_side
    # Nothing stored changed: not a message, not the Thread.
    assert await _stored(db, thread_id) == stored
    # Nobody was told.
    assert published[before:] == []
    assert await _notifications(db, woman_id) == her_notifications
    assert await _cleared_for(db, thread_id) == {man_id}
    # Moderation (T-9.1's report, T-9.5's admin view) reads the Thread with no
    # viewer's clearing applied, and finds every message, the original included.
    every = await messages_repository.page(
        db, thread_id, woman_id, since=None, after=None, limit=10
    )
    assert [row.Message.body_raw for row in every] == [
        "raw Unread by him",
        "raw Hello you",
        "raw Hi",
    ]


async def test_a_message_after_clearing_brings_the_thread_back_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, "Before", ago=timedelta(hours=1))
    assert (await _clear(client, token, thread.id)).status_code == 204

    await _say(db, thread, woman, "After")
    rows = (await client.get("/v1/threads", headers=bearer(token))).json()["items"]

    assert [row["id"] for row in rows] == [str(thread.id)]
    assert rows[0]["unread"] == 1
    assert rows[0]["last_message"]["text"] == "After"
    assert await _bodies(client, token, thread.id) == ["After"]


async def test_a_thread_with_no_messages_comes_back_with_its_first(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)

    assert (await _clear(client, token, thread.id)).status_code == 204
    hidden = await _list_ids(client, token)
    await _say(db, thread, woman, "First")

    assert hidden == []
    assert await _list_ids(client, token) == [str(thread.id)]
    assert await _bodies(client, token, thread.id) == ["First"]


async def test_cleared_at_is_the_newest_message_never_the_tap(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-610: the clearing is a point in the messages' own clock. The newest
    message is an hour old, and the clearing sits on it, not at the tap."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    talked = await make_thread(man, woman)
    silent = await make_thread(man, (await make_user(Gender.FEMALE))[0])
    await _say(db, talked, woman, "Older", ago=timedelta(hours=3))
    newest = await _say(db, talked, woman, "Newest", ago=timedelta(hours=1))

    for thread in (talked, silent):
        assert (await _clear(client, token, thread.id)).status_code == 204

    rows = await db.execute(
        select(ThreadClear.thread_id, ThreadClear.cleared_at).where(
            ThreadClear.user_id == man.id
        )
    )
    cleared = {thread_id: at for thread_id, at in rows}
    assert cleared == {talked.id: newest.created_at, silent.id: silent.created_at}


async def test_clearing_again_changes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, ago=timedelta(hours=1))

    first = await _clear(client, token, thread.id)
    once = await db.scalar(select(ThreadClear.cleared_at))
    again = await _clear(client, token, thread.id)

    assert first.status_code == again.status_code == 204
    assert await db.scalar(select(func.count()).select_from(ThreadClear)) == 1
    assert await db.scalar(select(ThreadClear.cleared_at)) == once


async def test_restoring_brings_back_the_whole_history(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """D-611: the clearing goes, not one step of it."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, "First", ago=timedelta(hours=3))
    assert (await _clear(client, token, thread.id)).status_code == 204
    await _say(db, thread, woman, "Second", ago=timedelta(hours=2))
    assert (await _clear(client, token, thread.id)).status_code == 204
    await _say(db, thread, woman, "Third", ago=timedelta(hours=1))
    assert await _bodies(client, token, thread.id) == ["Third"]

    restored = await _restore(client, token, thread.id)
    again = await _restore(client, token, thread.id)

    assert restored.status_code == again.status_code == 204
    assert restored.content == b""
    assert await _bodies(client, token, thread.id) == ["Third", "Second", "First"]
    assert await _cleared_for(db, thread.id) == set()


async def test_restoring_mine_leaves_hers(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    thread = await make_thread(man, woman)
    await _say(db, thread, woman, ago=timedelta(hours=1))
    assert (await _clear(client, token, thread.id)).status_code == 204
    assert (await _clear(client, her_token, thread.id)).status_code == 204

    assert (await _restore(client, token, thread.id)).status_code == 204

    assert await _cleared_for(db, thread.id) == {woman.id}
    assert await _list_ids(client, her_token) == []


@pytest.mark.parametrize("how", ["clear", "restore"])
@pytest.mark.parametrize(
    "whose", ["theirs", "nobody's", "blocked by me", "blocking me"]
)
async def test_only_my_threads_and_never_across_a_block(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    how: str,
    whose: str,
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    if whose == "theirs":
        thread_id = (await make_thread((await make_user())[0], woman)).id
    elif whose == "nobody's":
        thread_id = uuid.uuid4()
    else:
        thread_id = (await make_thread(man, woman)).id
        if whose == "blocked by me":
            await block(db, man, woman)
        else:
            await block(db, woman, man)

    response = await (_clear if how == "clear" else _restore)(client, token, thread_id)

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert await _cleared_for(db, thread_id) == set()


# --- Many at once -------------------------------------------------------------------


async def test_chosen_ids_clear_mine_and_skip_the_rest(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    one = await make_thread(man, (await make_user(Gender.FEMALE))[0])
    two = await make_thread(man, (await make_user(Gender.FEMALE))[0])
    blocker, _ = await make_user(Gender.FEMALE)
    across = await make_thread(man, blocker)
    await block(db, blocker, man)
    theirs = await make_thread(
        (await make_user())[0], (await make_user(Gender.FEMALE))[0]
    )
    ids = [one.id, two.id, one.id, across.id, theirs.id, uuid.uuid4()]

    response = await _clear_many(client, token, {"thread_ids": [str(i) for i in ids]})

    assert response.status_code == 200, response.text
    assert response.json() == {"cleared": 2}
    assert await _cleared_for(db, one.id) == {man.id}
    assert await _cleared_for(db, two.id) == {man.id}
    assert await _cleared_for(db, across.id) == set()
    assert await _cleared_for(db, theirs.id) == set()


async def test_clear_expired_takes_those_in_my_list_expired_by_the_clock(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()

    async def her() -> User:
        return (await make_user(Gender.FEMALE))[0]

    expired = await make_thread(man, await her(), status="expired")
    # Past its expiry before the cron has caught its status up (D-560).
    ran_out = await make_thread(man, await her())
    await db.execute(
        update(Thread)
        .where(Thread.id == ran_out.id)
        .values(expires_at=clock.now() - timedelta(minutes=1))
    )
    live = await make_thread(man, await her())
    knot = await make_thread(man, await her(), status="knotted")
    private = await make_thread(man, await her(), origin="dm")
    # Already cleared with nothing newer: not in my list, so not counted.
    hidden = await make_thread(man, await her(), status="expired")
    db.add(ThreadClear(user_id=man.id, thread_id=hidden.id, cleared_at=clock.now()))
    blocker = await her()
    across = await make_thread(man, blocker, status="expired")
    await block(db, man, blocker)
    theirs = await make_thread((await make_user())[0], await her(), status="expired")
    await db.flush()
    hidden_at = await db.scalar(
        select(ThreadClear.cleared_at).where(ThreadClear.thread_id == hidden.id)
    )

    response = await _clear_many(client, token, {"expired": True})

    assert response.status_code == 200, response.text
    assert response.json() == {"cleared": 2}
    mine = set(
        await db.scalars(
            select(ThreadClear.thread_id).where(ThreadClear.user_id == man.id)
        )
    )
    assert mine == {expired.id, ran_out.id, hidden.id}
    for untouched in (live, knot, private, across, theirs):
        assert await _cleared_for(db, untouched.id) == set()
    assert (
        await db.scalar(
            select(ThreadClear.cleared_at).where(ThreadClear.thread_id == hidden.id)
        )
        == hidden_at
    )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"thread_ids": []},
        {"expired": False},
        {"thread_ids": [str(uuid.uuid4())], "expired": True},
        {"thread_ids": [str(uuid.uuid4()) for _ in range(CLEAR_MAX + 1)]},
        {"thread_ids": ["not-an-id"]},
        {"expired": True, "everything": True},
    ],
)
async def test_a_bad_body_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, body: dict[str, Any]
) -> None:
    _, token = await make_user()

    response = await _clear_many(client, token, body)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await db.scalar(select(func.count()).select_from(ThreadClear)) == 0


async def test_a_full_hundred_is_taken(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    response = await _clear_many(
        client, token, {"thread_ids": [str(uuid.uuid4()) for _ in range(CLEAR_MAX)]}
    )

    assert response.status_code == 200
    assert response.json() == {"cleared": 0}


# --- Who may --------------------------------------------------------------------------


async def test_clearing_and_restoring_share_one_rate_limit(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    for _ in range(CLEARS_PER_MINUTE // 2):
        await _clear(client, token, uuid.uuid4())
        await _restore(client, token, uuid.uuid4())

    response = await _clear_many(client, token, {"expired": True})

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


@pytest.mark.parametrize("route", ["one", "many", "restore"])
async def test_onboarding_comes_first_and_signing_in_before_it(
    client: AsyncClient, make_user: MakeUser, route: str
) -> None:
    _, token = await make_user(onboarded=False)
    thread_id = uuid.uuid4()

    async def call(headers: dict[str, str]) -> Response:
        if route == "one":
            return await client.post(f"/v1/threads/{thread_id}/clear", headers=headers)
        if route == "many":
            return await client.post(
                "/v1/threads/clear", json={"expired": True}, headers=headers
            )
        return await client.delete(f"/v1/threads/{thread_id}/clear", headers=headers)

    unfinished = await call(bearer(token))
    signed_out = await call({})

    assert unfinished.status_code == 403
    assert error(unfinished)["code"] == "ONBOARDING_INCOMPLETE"
    assert signed_out.status_code == 401
    assert error(signed_out)["code"] == "AUTH_REQUIRED"
