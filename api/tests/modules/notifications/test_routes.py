"""The notification routes (T-9.4, 04-API "Notifications"): the VAPID key, push
subscriptions, the settings, and the in-app list.

A subscription names a push service the worker will POST to, so only the known
ones are taken (D-855): anything else is `VALIDATION_ERROR`, before a row. The
list is the caller's own, and leaves out anything about someone either of them
has blocked (P-760)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now as clock_now
from app.core.enums import Gender
from app.core.errors import AppError
from app.modules.notifications import service
from app.modules.notifications.models import Notification, PushSubscription
from app.modules.notifications.router import SUBSCRIBES_PER_MINUTE
from app.modules.notifications.rules import SUBSCRIPTIONS_KEPT
from app.modules.safety.models import Block
from tests.conftest import MakeThread, MakeUser, make_test_settings
from tests.modules.discovery.support import bearer, error
from tests.modules.notifications.support import (
    FCM,
    subscribe,
    subscribed,
    subscription_body,
)

pytestmark = pytest.mark.usefixtures("test_redis")

ROUTES = (
    ("GET", "/v1/push/key"),
    ("POST", "/v1/push/subscriptions"),
    ("DELETE", "/v1/push/subscriptions"),
    ("GET", "/v1/notification-prefs"),
    ("PATCH", "/v1/notification-prefs"),
    ("GET", "/v1/notifications"),
    ("POST", "/v1/notifications/read"),
)


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_every_route_needs_a_signed_in_user(
    db: AsyncSession, client: AsyncClient, method: str, path: str
) -> None:
    response = await client.request(method, path, json={})
    assert response.status_code == 401
    assert error(response)["code"] == "AUTH_REQUIRED"


# --- The key ------------------------------------------------------------------------


async def test_without_web_push_there_is_no_key(
    client: AsyncClient, make_user: MakeUser
) -> None:
    """D-856: local and CI run the fake, so the web offers no push."""
    _, token = await make_user()
    response = await client.get("/v1/push/key", headers=bearer(token))
    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"


def test_with_web_push_the_key_is_the_public_one() -> None:
    settings = make_test_settings().model_copy(
        update={"PUSH_PROVIDER": "webpush", "VAPID_PUBLIC_KEY": "BPublic"}
    )
    assert service.push_key(settings).public_key == "BPublic"
    with pytest.raises(AppError):
        service.push_key(settings.model_copy(update={"VAPID_PUBLIC_KEY": ""}))


# --- Subscriptions ------------------------------------------------------------------


async def _subscriptions(db: AsyncSession, endpoint: str) -> list[PushSubscription]:
    rows = await db.scalars(
        select(PushSubscription)
        .where(PushSubscription.endpoint == endpoint)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def test_a_subscription_is_kept_with_its_keys_and_never_returned(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    body = subscription_body()

    response = await subscribe(client, token, body)

    assert response.status_code == 201
    assert response.json() == {"endpoint": body["endpoint"]}
    [row] = await _subscriptions(db, body["endpoint"])
    assert (row.user_id, row.p256dh, row.auth) == (
        user.id,
        body["keys"]["p256dh"],
        body["keys"]["auth"],
    )


async def test_an_endpoint_moves_to_whoever_subscribed_it_last(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """One browser, a second account signed in on it: one row, the newer
    account's, so the first is never pushed on a browser it left."""
    _, first = await make_user()
    second, second_token = await make_user(Gender.FEMALE)
    body = subscription_body()
    assert (await subscribe(client, first, body)).status_code == 201
    again = subscription_body(body["endpoint"])

    assert (await subscribe(client, second_token, again)).status_code == 201

    [row] = await _subscriptions(db, body["endpoint"])
    assert (row.user_id, row.p256dh) == (second.id, again["keys"]["p256dh"])


async def test_only_the_newest_subscriptions_are_kept(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """One per browser, `SUBSCRIPTIONS_KEPT` at most: a subscribe beyond them
    drops the oldest."""
    user, token = await make_user()
    older = []
    for n in range(SUBSCRIPTIONS_KEPT):
        row = await subscribed(db, user.id)
        row.created_at = clock_now() - timedelta(days=SUBSCRIPTIONS_KEPT - n)
        older.append(row.endpoint)
    await db.flush()
    body = subscription_body()

    assert (await subscribe(client, token, body)).status_code == 201

    kept = await db.scalars(
        select(PushSubscription.endpoint).where(PushSubscription.user_id == user.id)
    )
    assert set(kept) == {*older[1:], body["endpoint"]}


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/x",  # not https
        "https://example.com/fcm/send/x",  # not a push service
        "https://fcm.googleapis.com.evil.example/x",  # a lookalike host
        "https://evilfcm.googleapis.com/x",  # a suffix without the dot
        "https://evilpush.apple.com/x",  # Apple's suffix without the dot
        "https://fcm.googleapis.com:8443/fcm/send/x",  # a port
        "https://user:pw@fcm.googleapis.com/fcm/send/x",  # credentials
        "https://169.254.169.254/latest/meta-data",  # the metadata service
        "https://127.0.0.1/x",
        "not a url",
    ],
)
async def test_an_endpoint_off_the_push_services_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, endpoint: str
) -> None:
    """D-855: the worker POSTs wherever the endpoint says, so only the push
    services' hosts are taken, exactly or after a dot."""
    _, token = await make_user()

    response = await subscribe(client, token, subscription_body(endpoint))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await _subscriptions(db, endpoint) == []


@pytest.mark.parametrize(
    "host",
    [
        "fcm.googleapis.com",
        "updates.push.services.mozilla.com",
        "web.push.apple.com",
        "api.push.apple.com",
        "wns2-par02p.notify.windows.com",
    ],
)
async def test_each_push_service_is_taken(
    client: AsyncClient, make_user: MakeUser, host: str
) -> None:
    _, token = await make_user()
    body = subscription_body(f"https://{host}/send/{uuid.uuid4().hex}")
    assert (await subscribe(client, token, body)).status_code == 201


@pytest.mark.parametrize(
    "keys",
    [
        {"p256dh": "AAAA", "auth": "AAAAAAAAAAAAAAAAAAAAAA"},  # too short
        {"p256dh": "B" + "A" * 86, "auth": "short"},  # auth not 16 bytes
        {"p256dh": "!!!", "auth": "AAAAAAAAAAAAAAAAAAAAAA"},  # not base64url
    ],
)
async def test_keys_that_are_not_keys_are_refused(
    client: AsyncClient, make_user: MakeUser, keys: dict[str, str]
) -> None:
    _, token = await make_user()
    body = {"endpoint": f"{FCM}{uuid.uuid4().hex}", "keys": keys}
    response = await subscribe(client, token, body)
    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_subscribing_is_rate_limited(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    for _ in range(SUBSCRIBES_PER_MINUTE):
        assert (await subscribe(client, token)).status_code == 201

    response = await subscribe(client, token)

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


async def test_unsubscribing_removes_only_your_own(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, mine = await make_user()
    other, theirs = await make_user(Gender.FEMALE)
    my_body, their_body = subscription_body(), subscription_body()
    await subscribe(client, mine, my_body)
    await subscribe(client, theirs, their_body)

    for endpoint in (my_body["endpoint"], their_body["endpoint"], my_body["endpoint"]):
        response = await client.request(
            "DELETE",
            "/v1/push/subscriptions",
            json={"endpoint": endpoint},
            headers=bearer(mine),
        )
        assert response.status_code == 204

    assert await _subscriptions(db, my_body["endpoint"]) == []
    [row] = await _subscriptions(db, their_body["endpoint"])
    assert row.user_id == other.id


# --- Settings -----------------------------------------------------------------------

DEFAULTS = {
    "match": True,
    "message": True,
    "like": True,
    "knot": True,
    "expiry": True,
    "balance": True,
    "gift": True,
    "album": True,
    "generic_text": False,
}


async def test_settings_start_on_with_names_shown(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    response = await client.get("/v1/notification-prefs", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == DEFAULTS


async def test_a_patch_changes_only_what_it_sends(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    response = await client.patch(
        "/v1/notification-prefs",
        json={"gift": False, "generic_text": True},
        headers=bearer(token),
    )
    assert response.status_code == 200
    assert response.json() == {**DEFAULTS, "gift": False, "generic_text": True}
    again = await client.get("/v1/notification-prefs", headers=bearer(token))
    assert again.json() == response.json()


@pytest.mark.parametrize(
    "body",
    [{}, {"gifts": False}, {"match": None}, {"match": "no"}, {"match": 0}],
)
async def test_a_patch_that_changes_nothing_or_names_nothing_is_refused(
    client: AsyncClient, make_user: MakeUser, body: dict[str, Any]
) -> None:
    _, token = await make_user()
    response = await client.patch(
        "/v1/notification-prefs", json=body, headers=bearer(token)
    )
    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


# --- The in-app list ----------------------------------------------------------------


async def _row(
    db: AsyncSession, user_id: uuid.UUID, kind: str, payload: dict[str, Any], n: int
) -> Notification:
    row = Notification(
        user_id=user_id,
        kind=kind,
        payload=payload,
        created_at=clock_now() + timedelta(seconds=n),
    )
    db.add(row)
    await db.flush()
    return row


async def _list(client: AsyncClient, token: str, **params: Any) -> Any:
    response = await client.get(
        "/v1/notifications", params=params, headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_list_is_your_own_newest_first_in_pages(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    other, _ = await make_user(Gender.FEMALE)
    rows = [await _row(db, user.id, "low_balance", {"balance": n}, n) for n in range(3)]
    await _row(db, other.id, "low_balance", {"balance": 9}, 9)

    first = await _list(client, token, limit=2)
    second = await _list(client, token, limit=2, cursor=first["next_cursor"])

    assert [item["id"] for item in first["items"]] == [str(rows[2].id), str(rows[1].id)]
    assert [item["id"] for item in second["items"]] == [str(rows[0].id)]
    assert second["next_cursor"] is None
    assert first["items"][0] == {
        "id": str(rows[2].id),
        "kind": "low_balance",
        "data": {"balance": 2},
        "read_at": None,
        "created_at": first["items"][0]["created_at"],
    }


async def test_reading_marks_every_unread_one_of_yours(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    other, _ = await make_user(Gender.FEMALE)
    mine = await _row(db, user.id, "low_balance", {}, 0)
    theirs = await _row(db, other.id, "low_balance", {}, 0)

    response = await client.post("/v1/notifications/read", headers=bearer(token))

    assert response.status_code == 204
    await db.refresh(mine)
    await db.refresh(theirs)
    assert mine.read_at is not None
    assert theirs.read_at is None
    [item] = (await _list(client, token))["items"]
    assert item["read_at"] is not None


@pytest.mark.parametrize("blocker", ["me", "them"])
async def test_nothing_about_someone_blocked_either_way_is_listed(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    make_thread: MakeThread,
    blocker: str,
) -> None:
    """P-760: a block hides every row about the other person, by the row's
    `user_id` or, with none, its Thread's other person (an hour running out);
    rows about anyone else and about nobody stay."""
    man, token = await make_user()
    blocked, _ = await make_user(Gender.FEMALE)
    friend, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, blocked)
    await _row(db, man.id, "match", {"user_id": str(blocked.id)}, 0)
    await _row(db, man.id, "thread_expiring", {"thread_id": str(thread.id)}, 1)
    # A gift's row names its sender (T-8.10): hidden across a block, as any is.
    await _row(db, man.id, "gift", {"gift_send_id": "g", "user_id": str(blocked.id)}, 1)
    kept_friend = await _row(db, man.id, "match", {"user_id": str(friend.id)}, 2)
    kept_nobody = await _row(db, man.id, "low_balance", {"balance": 3}, 3)
    pair = (man.id, blocked.id) if blocker == "me" else (blocked.id, man.id)
    db.add(Block(blocker_id=pair[0], blocked_id=pair[1]))
    await db.flush()

    items = (await _list(client, token))["items"]

    assert [item["id"] for item in items] == [str(kept_nobody.id), str(kept_friend.id)]


async def test_the_block_filter_is_what_hides_them(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, make_thread: MakeThread
) -> None:
    """The same rows with no block are all listed: the filter, not the rows'
    shape, is what hid them above."""
    man, token = await make_user()
    other, _ = await make_user(Gender.FEMALE)
    thread = await make_thread(man, other)
    await _row(db, man.id, "match", {"user_id": str(other.id)}, 0)
    await _row(db, man.id, "thread_expiring", {"thread_id": str(thread.id)}, 1)

    assert len((await _list(client, token))["items"]) == 2
