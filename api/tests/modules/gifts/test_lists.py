"""The gifts' reads (T-8.9, D-652): `GET /v1/gifts`, the catalogue held 60 s
and a man's free sends read fresh; `GET /v1/me/gifts`, what she received, with
each sender's card and never what he paid; `GET /v1/users/{id}/gifts`, counts
only, under D-493's rule and her `show_gifts`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, UserStatus
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.discovery.support import bearer, block, error, photo
from tests.modules.gifts.support import price, sent, set_config, token_for

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # Thursday, 12:00 IST
NEXT_MONDAY = datetime(2026, 10, 11, 18, 30, tzinfo=UTC)  # 00:00 IST (D-650)
THE_FOUR = [
    {"id": "coffee", "label": "Coffee", "asset": "☕", "credits": 5},
    {"id": "rose", "label": "Rose", "asset": "🌹", "credits": 10},
    {"id": "chocolate", "label": "Chocolate", "asset": "🍫", "credits": 15},
    {"id": "teddy", "label": "Teddy", "asset": "🧸", "credits": 20},
]


async def _get(client: AsyncClient, token: str, path: str, **params: Any) -> Any:
    response = await client.get(path, params=params, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


# --- GET /gifts ----------------------------------------------------------------------


async def test_a_man_sees_the_four_and_his_free_sends_left(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    _man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)

    before = await _get(client, token, "/v1/gifts")
    await sent(client, token, woman.id, "rose")
    after = await _get(client, token, "/v1/gifts")

    assert before == {
        "gifts": THE_FOUR,
        "free_sends_left": 15,
        "free_sends_reset_at": NEXT_MONDAY.isoformat().replace("+00:00", "Z"),
    }
    assert after["free_sends_left"] == 14


async def test_none_left_is_zero_never_below(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await set_config(db, "gift_free_weekly_limit", 1)
    _man, token = await make_user(credits=20)
    woman, _ = await make_user(Gender.FEMALE)
    await sent(client, token, woman.id, "rose")
    await sent(client, token, woman.id, "coffee", shown=5)

    assert (await _get(client, token, "/v1/gifts"))["free_sends_left"] == 0


async def test_a_woman_sees_the_gifts_and_no_free_sends(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(Gender.FEMALE)

    assert await _get(client, token, "/v1/gifts") == {
        "gifts": THE_FOUR,
        "free_sends_left": None,
        "free_sends_reset_at": None,
    }


async def test_the_catalogue_is_held_a_minute_and_a_send_reads_the_row(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """P-47's minute for what is shown; a send is priced fresh, so a screen
    showing the held price is refused with the new one (D-600)."""
    clock.freeze(NOON)
    await set_config(db, "gift_free_weekly_limit", 0)
    man, token = await make_user(credits=30)
    man_id = man.id
    woman, _ = await make_user(Gender.FEMALE)
    await _get(client, token, "/v1/gifts")
    await price(db, "rose", 12)

    clock.advance(timedelta(seconds=59))
    held = await _get(client, token, "/v1/gifts")
    assert held["gifts"][1]["credits"] == 10
    refused = await client.post(
        "/v1/gifts/send",
        json={"recipient_id": str(woman.id), "gift_id": "rose", "shown_price": 10},
        headers={**bearer(token), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert refused.status_code == 409
    assert error(refused)["details"] == {"price": 12}

    clock.advance(timedelta(seconds=1))
    fresh = await _get(client, token_for(man_id), "/v1/gifts")
    assert fresh["gifts"][1]["credits"] == 12


# --- GET /me/gifts ---------------------------------------------------------------------


async def test_she_sees_what_she_received_newest_first_never_the_price(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    await set_config(db, "gift_free_weekly_limit", 1)
    one, one_token = await make_user(credits=20)
    two, _two_token = await make_user()
    woman, _her_token = await make_user(Gender.FEMALE)
    one_id, two_id, woman_id = one.id, two.id, woman.id
    shown = await photo(db, one)
    first = await sent(client, one_token, woman_id, "rose")
    clock.advance(timedelta(minutes=1))
    paid = await sent(client, token_for(one_id), woman_id, "coffee", shown=5)
    clock.advance(timedelta(minutes=1))
    last = await sent(client, token_for(two_id), woman_id, "teddy")

    page = await _get(client, token_for(woman_id), "/v1/me/gifts")

    assert [item["id"] for item in page["items"]] == [
        last["id"],
        paid["id"],
        first["id"],
    ]
    assert page["next_cursor"] is None
    item = page["items"][1]
    assert set(item) == {"id", "gift_id", "sender", "created_at"}
    assert item["gift_id"] == "coffee"
    assert item["sender"] == {
        "id": str(one_id),
        "first_name": "Test",
        "username": item["sender"]["username"],
        "main_photo_url": item["sender"]["main_photo_url"],
        "shows_badge": False,
        "is_online": True,  # he was active a minute ago, sending it
        "deleted": False,
    }
    assert item["sender"]["main_photo_url"].endswith(str(shown.public_key))
    assert "credits" not in str(page)


async def test_her_list_pages_by_cursor(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    woman, _ = await make_user(Gender.FEMALE)
    woman_id = woman.id
    ids = []
    for gift in ("coffee", "rose", "chocolate"):
        man, _ = await make_user()
        ids.append((await sent(client, token_for(man.id), woman_id, gift))["id"])
        clock.advance(timedelta(seconds=1))
    token = token_for(woman_id)

    first = await _get(client, token, "/v1/me/gifts", limit=2)
    second = await _get(
        client, token, "/v1/me/gifts", limit=2, cursor=first["next_cursor"]
    )

    assert [i["id"] for i in first["items"]] == ids[:0:-1]
    assert [i["id"] for i in second["items"]] == ids[:1]
    assert second["next_cursor"] is None


async def test_a_deleted_sender_is_a_card_with_no_name(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    man_id = man.id
    await sent(client, token, woman.id)
    await db.execute(
        update(User).where(User.id == man_id).values(status=UserStatus.DELETED)
    )

    [item] = (await _get(client, her_token, "/v1/me/gifts"))["items"]

    assert item["sender"]["deleted"] is True
    assert (item["sender"]["first_name"], item["sender"]["username"]) == (None, None)


@pytest.mark.parametrize("who", ["she blocked him", "he blocked her"])
async def test_gifts_from_across_a_block_are_left_out(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, who: str
) -> None:
    man, token = await make_user()
    _other, other_token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    await sent(client, token, woman.id)
    kept = await sent(client, other_token, woman.id)
    if who == "she blocked him":
        await block(db, woman, man)
    else:
        await block(db, man, woman)

    page = await _get(client, her_token, "/v1/me/gifts")

    assert [i["id"] for i in page["items"]] == [kept["id"]]


async def test_a_man_received_none(client: AsyncClient, make_user: MakeUser) -> None:
    _, token = await make_user()

    assert await _get(client, token, "/v1/me/gifts") == {
        "items": [],
        "next_cursor": None,
    }


# --- GET /users/{id}/gifts -------------------------------------------------------------


async def test_anyone_who_can_open_her_profile_sees_her_counts(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _one, one_token = await make_user()
    _two, two_token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    _viewer, viewer_token = await make_user(Gender.FEMALE)
    await sent(client, one_token, woman.id, "teddy")
    await sent(client, one_token, woman.id, "rose")
    await sent(client, two_token, woman.id, "rose")

    found = await _get(client, viewer_token, f"/v1/users/{woman.id}/gifts")

    assert found == {
        "counts": [{"gift_id": "rose", "count": 2}, {"gift_id": "teddy", "count": 1}]
    }


async def test_show_gifts_off_hides_them_from_all_but_her(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _man, token = await make_user()
    woman, her_token = await make_user(Gender.FEMALE)
    woman_id = woman.id
    await sent(client, token, woman_id, "rose")
    await db.execute(
        update(Profile).where(Profile.user_id == woman_id).values(show_gifts=False)
    )

    assert await _get(client, token, f"/v1/users/{woman_id}/gifts") == {"counts": []}
    assert await _get(client, her_token, f"/v1/users/{woman_id}/gifts") == {
        "counts": [{"gift_id": "rose", "count": 1}]
    }


async def test_counts_across_a_block_are_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user()
    woman, _ = await make_user(Gender.FEMALE)
    await block(db, woman, man)

    blocked = await client.get(f"/v1/users/{woman.id}/gifts", headers=bearer(token))
    nobody = await client.get(f"/v1/users/{uuid.uuid4()}/gifts", headers=bearer(token))

    assert blocked.status_code == nobody.status_code == 404
    assert error(blocked) == error(nobody)
