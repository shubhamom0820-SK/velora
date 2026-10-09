"""Who calls `notify()` (T-9.4), through the app as a person would: each kind is
written where the thing it tells becomes true, with what its push needs.

P-631: a new album request tells her (`album.requested` and `album_request`);
P-550: a gift's push follows the `gift` setting; a like is a push only; a
message's push goes to the recipient, never twice for a Thread's opening; a
balance falling under `low_balance_velas` (10) tells him once."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import Gender, LedgerReason
from app.modules.notifications.models import NotificationPrefs
from app.modules.wallet import service as wallet_service
from tests.conftest import MakeThread, MakeUser
from tests.modules.album.support import album_of, asked, decide
from tests.modules.discovery.support import HERE, bearer, north, person
from tests.modules.gifts.support import sent
from tests.modules.notifications.support import in_app, outbox, subscribed

pytestmark = pytest.mark.usefixtures("test_redis")


async def _swipe(
    client: AsyncClient,
    token: str,
    target: uuid.UUID,
    direction: str,
    shown: int | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"target_id": str(target), "dir": direction}
    if shown is not None:
        body["shown_price"] = shown
    response = await client.post("/v1/swipes", json=body, headers=bearer(token))
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_a_like_is_a_push_to_her_naming_him(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await person(db, make_user, Gender.MALE, at=HERE)
    woman, _ = await person(db, make_user, at=north(1))
    man_id, woman_id = man.id, woman.id
    await subscribed(db, woman_id)

    await _swipe(client, token, woman_id, "like", None)

    assert await in_app(db, woman_id) == []
    assert await outbox(db, woman_id) == [
        ("like", {"user_id": str(man_id), "super": False})
    ]


async def test_a_super_like_to_him_never_names_her(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, _ = await person(db, make_user, Gender.MALE, at=HERE)
    _, token = await person(db, make_user, at=north(1))
    man_id = man.id
    await subscribed(db, man_id)

    await _swipe(client, token, man_id, "super", None)

    assert await outbox(db, man_id) == [("like", {"super": True})]


async def test_a_like_back_is_a_match_not_a_like(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await person(db, make_user, Gender.MALE, at=HERE)
    woman, her_token = await person(db, make_user, at=north(1))
    man_id, woman_id = man.id, woman.id
    await subscribed(db, woman_id)
    await _swipe(client, her_token, man_id, "like", None)

    body = await _swipe(client, token, woman_id, "like", None)

    match = {"match_id": body["match_id"], "user_id": str(man_id)}
    assert await in_app(db, woman_id) == [("match", match)]
    assert await outbox(db, woman_id) == [("match", match)]


async def test_a_match_wakes_the_worker_once_after_the_commit(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    """D-850: a wake on `wake:send_push` is queued beside each push, with the
    request's events, after its commit (`events.publish` sends one of them:
    `test_one_wake_is_published_however_many_were_queued`)."""
    man, token = await person(db, make_user, Gender.MALE, at=HERE)
    woman, her_token = await person(db, make_user, at=north(1))
    man_id, woman_id = man.id, woman.id
    for each in (man_id, woman_id):
        await subscribed(db, each)
    await _swipe(client, her_token, man_id, "like", None)
    published.clear()

    await _swipe(client, token, woman_id, "like", None)

    wakes = [each for each in published if each.type == events.PUSH_WAKE]
    assert len(wakes) == 2  # queued for each of the two
    assert {each.channel for each in wakes} == {"wake:send_push"}


async def test_a_new_album_request_tells_her(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    """P-631: an `album.requested` event and an `album_request` notification at
    the request's commit; then her answer tells him."""
    man, token = await make_user(credits=3)
    woman, her_token = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)
    await subscribed(db, woman_id)
    await subscribed(db, man_id)

    body = await asked(client, token, woman_id)

    told = {"album_request_id": body["id"], "user_id": str(man_id)}
    assert [
        (e.user_id, e.type, e.data) for e in published if e.type == "album.requested"
    ] == [(woman_id, "album.requested", told)]
    assert await in_app(db, woman_id) == [("album_request", told)]
    assert await outbox(db, woman_id) == [("album_request", told)]

    assert (await decide(client, her_token, body["id"], True)).status_code == 200
    decided = {
        "album_request_id": body["id"],
        "user_id": str(woman_id),
        "granted": True,
    }
    assert await in_app(db, man_id) == [("album_decided", decided)]


async def test_a_gifts_push_follows_the_gift_setting(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """P-550: off, the gift still shows in her list; no push waits."""
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await subscribed(db, woman_id)
    await db.execute(
        update(NotificationPrefs)
        .where(NotificationPrefs.user_id == woman_id)
        .values(gift=False)
    )

    body = await sent(client, token, woman_id)

    gift = {"gift_send_id": body["id"], "gift_id": "coffee", "user_id": str(man_id)}
    assert await in_app(db, woman_id) == [("gift", gift)]
    assert await outbox(db, woman_id) == []


async def _write(client: AsyncClient, token: str, thread_id: uuid.UUID) -> None:
    response = await client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "kind": "text", "body": "Hello"},
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text


async def test_a_message_is_a_push_to_the_recipient_without_its_text(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, _ = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    thread = await make_thread(man, woman)
    thread_id = thread.id
    await subscribed(db, man_id)
    await subscribed(db, woman_id)

    await _write(client, her_token, thread_id)

    assert await outbox(db, man_id) == [
        ("message", {"thread_id": str(thread_id), "user_id": str(woman_id)})
    ]
    assert await in_app(db, man_id) == []
    assert await outbox(db, woman_id) == []


async def test_an_opening_with_a_first_message_is_one_push(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=12)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await subscribed(db, woman_id)

    response = await client.post(
        "/v1/threads",
        json={"user_id": str(woman_id), "first_message": "Hi", "shown_price": 8},
        headers=bearer(token),
    )

    assert response.status_code == 200, response.text
    opened = {"thread_id": response.json()["id"], "user_id": str(man_id)}
    assert await outbox(db, woman_id) == [("thread", opened)]


async def test_a_knot_asked_tells_the_other(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    thread = await make_thread(man, woman)
    thread_id = thread.id
    await subscribed(db, woman_id)

    response = await client.post(f"/v1/threads/{thread_id}/knot", headers=bearer(token))

    assert response.status_code == 200, response.text
    asked_for = {"thread_id": str(thread_id), "user_id": str(man_id)}
    assert await outbox(db, woman_id) == [("knot_requested", asked_for)]


async def test_a_balance_falling_under_ten_tells_him_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-853: from 10 or more to under 10, once; a debit already under it, no."""
    man, token = await person(db, make_user, Gender.MALE, at=HERE)
    man_id = man.id
    await _grant(db, man_id, 16)
    first, _ = await person(db, make_user, at=north(1))
    second, _ = await person(db, make_user, at=north(2))
    third, _ = await person(db, make_user, at=north(3))

    await _swipe(client, token, first.id, "super", 5)  # 16 → 11
    assert await in_app(db, man_id) == []
    await _swipe(client, token, second.id, "super", 5)  # 11 → 6
    assert await in_app(db, man_id) == [("low_balance", {"balance": 6})]
    await _swipe(client, token, third.id, "super", 5)  # 6 → 1
    assert await in_app(db, man_id) == [("low_balance", {"balance": 6})]


async def _grant(db: AsyncSession, user_id: uuid.UUID, credits: int) -> None:
    await wallet_service.credit(
        db, user_id, credits, LedgerReason.ADMIN_GRANT, event=f"test-{uuid.uuid4()}"
    )
    await db.flush()
