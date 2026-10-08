"""`GET /v1/likes` and `GET /v1/likes/count` (T-6.7, D-542): everyone who
liked or Super Liked you and whom you haven't swiped, from someone you could
swipe back. A woman sees each, free (D-002); a man, until he reveals one,
sees a handle, whether it was a Super Like, and the server's blur of their main
photo: never their id, name, username or photo, anywhere in the answer."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FraudBand, Gender, OnboardingStep, Seeking, UserStatus
from app.core.queue import FakeQueue
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings
from tests.modules.discovery.support import (
    banded,
    bearer,
    block,
    error,
    north,
    person,
    photo,
    swipe,
)

pytestmark = pytest.mark.usefixtures("test_redis")

CARD_FIELDS = {"handle", "is_super", "card", "blurred_photo_url"}


async def _likes(client: AsyncClient, token: str, **params: Any) -> Response:
    return await client.get("/v1/likes", params=params, headers=bearer(token))


async def _items(client: AsyncClient, token: str) -> list[dict[str, Any]]:
    response = await _likes(client, token, limit=50)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    for item in items:
        assert set(item) == CARD_FIELDS
    return items


async def _count(client: AsyncClient, token: str) -> int:
    response = await client.get("/v1/likes/count", headers=bearer(token))
    assert response.status_code == 200, response.text
    found: int = response.json()["count"]
    return found


async def _reveal_row(db: AsyncSession, viewer: User, liker: User) -> None:
    await db.execute(
        text("INSERT INTO liked_you_reveals (viewer_id, liker_id) VALUES (:v, :l)"),
        {"v": viewer.id, "l": liker.id},
    )


async def _blurred(db: AsyncSession, photo_id: uuid.UUID, key: str) -> None:
    await db.execute(
        text("UPDATE photos SET blur_key = :k WHERE id = :id"),
        {"k": key, "id": photo_id},
    )


def _url(key: str) -> str:
    return f"{make_test_settings().PUBLIC_CDN_URL}/{key}"


# --- What a man sees ------------------------------------------------------------------


async def test_a_man_sees_who_liked_him_as_a_blur_and_nothing_that_names_them(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The paywall's whole point: nothing in the answer, its cursor decoded
    included, names her, links to her or shows her."""
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(
        db, make_user, at=north(2), first_name="Zeenat", username="zeenat_k"
    )
    main = await photo(db, her, place=0)
    await photo(db, her, place=1)
    await _blurred(db, main.id, "b/0b7a2f1e-0000-4000-8000-000000000001.jpg")
    await swipe(db, her, me, "like")
    her_id, main_id = str(her.id), str(main.id)

    response = await _likes(client, token, limit=1)
    assert response.status_code == 200, response.text
    body = response.json()

    [item] = body["items"]
    assert item["card"] is None
    assert item["is_super"] is False
    assert item["blurred_photo_url"] == _url(
        "b/0b7a2f1e-0000-4000-8000-000000000001.jpg"
    )
    assert len(item["handle"]) == 32
    every = response.text
    if body["next_cursor"]:
        every += base64.urlsafe_b64decode(body["next_cursor"] + "==").decode()
    for secret in (her_id, her_id.replace("-", ""), "Zeenat", "zeenat_k", main_id):
        assert secret not in every


async def test_the_cursor_names_nobody_either(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    likers = [(await person(db, make_user, at=north(1)))[0] for _ in range(3)]
    for liker in likers:
        await swipe(db, liker, me, "like")
    ids = [str(liker.id) for liker in likers]

    body = (await _likes(client, token, limit=1)).json()

    cursor = base64.urlsafe_b64decode(body["next_cursor"] + "==").decode()
    assert not any(user_id in cursor for user_id in ids)
    assert json.loads(cursor)[1] == body["items"][0]["handle"]


async def test_a_super_like_says_so(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "super")

    [item] = await _items(client, token)

    assert item["is_super"] is True


async def test_a_revealed_one_is_a_card(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(3), first_name="Noor")
    await swipe(db, her, me, "like")
    await _reveal_row(db, me, her)
    her_id = str(her.id)

    [item] = await _items(client, token)

    assert item["card"]["id"] == her_id
    assert item["card"]["first_name"] == "Noor"
    assert item["card"]["distance_km"] == 3
    assert item["blurred_photo_url"] is None


async def test_no_photo_is_no_blur(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")

    [item] = await _items(client, token)

    assert (item["card"], item["blurred_photo_url"]) == (None, None)


async def test_a_main_photo_with_no_blur_yet_is_queued_for_one(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, fake_queue: FakeQueue
) -> None:
    """Photos approved before T-6.7 have no blur: the list asks for one."""
    me, token = await person(db, make_user, Gender.MALE)
    her, _ = await person(db, make_user, at=north(1))
    main = await photo(db, her, place=0)
    await swipe(db, her, me, "like")

    [item] = await _items(client, token)

    assert item["blurred_photo_url"] is None
    assert [job.job_id for job in fake_queue.named("blur_photo")] == [
        f"blur_photo:{main.id}"
    ]


# --- What a woman sees (D-002) ----------------------------------------------------------


async def test_a_woman_sees_everyone_who_liked_her_free(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.FEMALE)
    him, _ = await person(db, make_user, Gender.MALE, at=north(1), first_name="Arjun")
    await swipe(db, him, me, "super")
    him_id = str(him.id)

    [item] = await _items(client, token)

    assert item["card"]["id"] == him_id
    assert item["card"]["first_name"] == "Arjun"
    assert (item["is_super"], item["blurred_photo_url"]) == (True, None)


# --- Who is listed --------------------------------------------------------------------


async def test_newest_first_and_pages_without_repeating_or_skipping(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.FEMALE)
    men = [(await person(db, make_user, Gender.MALE, at=north(1)))[0] for _ in range(7)]
    for n, man in enumerate(men):
        await swipe(db, man, me, "like")
        await db.execute(
            text(
                "UPDATE swipes SET created_at = now() - make_interval(mins => :n)"
                " WHERE swiper_id = :a AND target_id = :b"
            ),
            {"n": n, "a": man.id, "b": me.id},
        )
    want = [str(man.id) for man in men]

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        body = (await _likes(client, token, **params)).json()
        seen += [item["card"]["id"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == want


async def test_only_likes_not_yet_answered_from_someone_i_could_swipe_back(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.FEMALE, seeking=Seeking.MEN)
    listed, _ = await person(db, make_user, Gender.MALE, at=north(1))
    passed_me, _ = await person(db, make_user, Gender.MALE, at=north(1))
    i_answered, _ = await person(db, make_user, Gender.MALE, at=north(1))
    i_passed, _ = await person(db, make_user, Gender.MALE, at=north(1))
    blocked, _ = await person(db, make_user, Gender.MALE, at=north(1))
    blocked_me, _ = await person(db, make_user, Gender.MALE, at=north(1))
    hidden, _ = await person(db, make_user, Gender.MALE, at=north(1), is_hidden=True)
    paused, _ = await person(db, make_user, Gender.MALE, at=north(1))
    frozen, _ = await person(db, make_user, Gender.MALE, at=north(1))
    unfinished, _ = await person(db, make_user, Gender.MALE, at=north(1))
    woman, _ = await person(
        db, make_user, Gender.FEMALE, at=north(1), seeking=Seeking.WOMEN
    )
    far, _ = await person(db, make_user, Gender.MALE, at=(12.97, 77.59))
    for liker in (
        listed,
        i_answered,
        i_passed,
        blocked,
        blocked_me,
        hidden,
        paused,
        frozen,
        unfinished,
        woman,
        far,
    ):
        await swipe(db, liker, me, "like")
    await swipe(db, passed_me, me, "pass")
    await swipe(db, me, i_answered, "like")
    await swipe(db, me, i_passed, "pass")
    await block(db, me, blocked)
    await block(db, blocked_me, me)
    paused.status = UserStatus.PAUSED
    unfinished.onboarding_step = OnboardingStep.SELFIE
    await banded(db, frozen, FraudBand.FREEZE)
    await db.flush()
    # Across India: a like reaches past the radius (D-492), so it is listed.
    want = {str(listed.id), str(far.id)}

    assert {item["card"]["id"] for item in await _items(client, token)} == want
    assert await _count(client, token) == 2


async def test_the_count_counts_what_the_list_lists_revealed_or_not(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.MALE)
    first, _ = await person(db, make_user, at=north(1))
    second, _ = await person(db, make_user, at=north(1))
    await swipe(db, first, me, "like")
    await swipe(db, second, me, "super")
    await _reveal_row(db, me, first)

    assert len(await _items(client, token)) == await _count(client, token) == 2


# --- Refusals -------------------------------------------------------------------------


async def test_an_edited_cursor_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    cursor = base64.urlsafe_b64encode(b'[1.0, "x"]').rstrip(b"=").decode()

    response = await _likes(client, token, cursor=cursor)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_likes_need_sign_in_and_onboarding_done(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    assert (await client.get("/v1/likes")).status_code == 401
    assert (await client.get("/v1/likes/count")).status_code == 401
    me, token = await person(db, make_user, Gender.MALE)
    me.onboarding_step = OnboardingStep.PHOTOS
    await db.flush()

    for path in ("/v1/likes", "/v1/likes/count"):
        response = await client.get(path, headers=bearer(token))
        assert error(response)["code"] == "ONBOARDING_INCOMPLETE"
