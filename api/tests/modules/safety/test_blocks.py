"""`POST /v1/blocks`, `DELETE /v1/blocks/{user_id}`, `GET /v1/blocks` (T-9.1,
D-860, D-863): anyone with an account may be blocked, visible or not; twice is
once; unblocking lifts the block and keeps its row, so blocking again is a new
one; the list is whom you block now, newest first, and never who blocks you."""

from __future__ import annotations

import base64
import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.enums import FraudBand, Gender, UserStatus
from app.core.providers import FakeProviders
from app.modules.notifications.models import Notification
from app.modules.safety.models import Block
from app.modules.safety.router import BLOCKS_PER_MINUTE
from tests.conftest import MakeUser
from tests.modules.discovery.support import banded, bearer, error, photo
from tests.modules.safety.support import (
    block,
    blocked,
    erased,
    rows,
    unblock,
    unblocked,
)

pytestmark = pytest.mark.usefixtures("test_redis")


async def _list(client: AsyncClient, token: str, **params: Any) -> dict[str, Any]:
    response = await client.get("/v1/blocks", params=params, headers=bearer(token))
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def test_a_block_is_made_and_answered_as_a_card(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    await photo(db, her, place=0)
    her_id = her.id

    response = await block(client, token, her_id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"user", "blocked_at"}
    assert body["user"]["id"] == str(her_id)
    assert body["user"]["first_name"] == "Test"
    assert body["user"]["deleted"] is False
    assert body["user"]["main_photo_url"] is not None
    [row] = await rows(db, me.id)
    assert (row.blocked_id, row.unblocked_at) == (her_id, None)


async def test_twice_is_once(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)

    first = await block(client, token, her.id)
    second = await block(client, token, her.id)

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert len(await rows(db, me.id)) == 1


async def test_anyone_with_an_account_may_be_blocked_whatever_they_are(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """A block needs no permission to see them: someone frozen, hidden,
    deleted or not yet onboarded is blocked all the same."""
    _, token = await make_user()
    frozen, _ = await make_user(Gender.FEMALE)
    await banded(db, frozen, FraudBand.FREEZE)
    gone, _ = await make_user(Gender.FEMALE)
    gone.status = UserStatus.DELETED
    new, _ = await make_user(Gender.FEMALE, onboarded=False)
    await db.flush()

    for other in (frozen, gone, new):
        assert (await block(client, token, other.id)).status_code == 201


async def test_nobody_is_not_found_and_yourself_is_not_allowed(
    client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    me_id = me.id

    nobody = await block(client, token, uuid.uuid4())
    assert nobody.status_code == 404
    assert error(nobody)["code"] == "NOT_FOUND"
    yourself = await block(client, token, me_id)
    assert yourself.status_code == 422
    assert error(yourself) == {
        "code": "NOT_ALLOWED",
        "message": "You can't block yourself.",
        "details": {"why": "yourself"},
    }


async def test_unblocking_keeps_the_row_and_blocking_again_is_a_new_one(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-860: "blocked by many people" stays a signal, so a lifted block is
    history, never deleted."""
    me, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    her_id = her.id

    await blocked(client, token, her_id)
    await unblocked(client, token, her_id)
    [lifted] = await rows(db, me.id)
    assert lifted.unblocked_at is not None
    assert (await _list(client, token))["items"] == []

    await blocked(client, token, her_id)
    history = await rows(db, me.id)
    assert len(history) == 2
    assert [r.unblocked_at is None for r in history] == [False, True]


async def test_unblocking_twice_or_someone_never_blocked_is_204(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    her_id = her.id
    await blocked(client, token, her_id)
    await unblocked(client, token, her_id)
    [first] = await rows(db, me.id)
    lifted_at = first.unblocked_at

    await unblocked(client, token, her_id)
    await unblocked(client, token, uuid.uuid4())

    [again] = await rows(db, me.id)
    assert again.unblocked_at == lifted_at


async def test_only_one_block_stands_per_pair_in_the_database(
    db: AsyncSession, make_user: MakeUser
) -> None:
    me, _ = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    db.add(Block(blocker_id=me.id, blocked_id=her.id))
    await db.flush()

    with pytest.raises(IntegrityError, match="uq_blocks_active"):
        async with db.begin_nested():
            db.add(Block(blocker_id=me.id, blocked_id=her.id))
            await db.flush()


async def test_the_list_is_whom_you_block_now_newest_first_never_who_blocks_you(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user()
    first, _ = await make_user(Gender.FEMALE)
    second, _ = await make_user(Gender.FEMALE)
    lifted, _ = await make_user(Gender.FEMALE)
    _, their_token = await make_user(Gender.FEMALE)
    ids = [first.id, second.id, lifted.id]
    me_id = me.id
    for other in ids:
        await blocked(client, token, other)
    await unblocked(client, token, lifted.id)
    await blocked(client, their_token, me_id)
    # One transaction writes every row with the same `now()`: spread them.
    for n, other in enumerate(ids):
        await db.execute(
            update(Block)
            .where(Block.blocked_id == other)
            .values(created_at=func.now() - timedelta(minutes=10 - n))
        )

    page = await _list(client, token)

    assert [item["user"]["id"] for item in page["items"]] == [
        str(second.id),
        str(first.id),
    ]
    assert page["next_cursor"] is None
    assert (await _list(client, their_token))["items"][0]["user"]["id"] == str(me_id)


async def test_the_list_pages_by_its_cursor_and_refuses_one_it_never_gave(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    for _n in range(3):
        other, _ = await make_user(Gender.FEMALE)
        await blocked(client, token, other.id)

    one = await _list(client, token, limit=2)
    two = await _list(client, token, limit=2, cursor=one["next_cursor"])

    seen = [i["user"]["id"] for i in one["items"] + two["items"]]
    assert len(seen) == len(set(seen)) == 3
    assert two["next_cursor"] is None
    for params in (
        {"cursor": base64.urlsafe_b64encode(b'["x"]').decode().rstrip("=")},
        {"limit": 0},
        {"limit": 51},
    ):
        response = await client.get("/v1/blocks", params=params, headers=bearer(token))
        assert response.status_code == 400, params
        assert error(response)["code"] == "VALIDATION_ERROR"


async def test_an_erased_person_is_still_listed_as_deleted_and_can_be_unblocked(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    """Their block holds against their number (D-861), so it stays the
    blocker's to lift, shown as a deleted account: no name, no photo."""
    _, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    her_id = her.id
    await blocked(client, token, her_id)
    await erased(db, her, fake_providers.storage)

    [item] = (await _list(client, token))["items"]

    assert item["user"] == {
        "id": str(her_id),
        "first_name": None,
        "username": None,
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": True,
    }
    await unblocked(client, token, her_id)
    assert (await _list(client, token))["items"] == []


async def test_blocks_and_unblocks_share_a_limit_a_minute(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    for n in range(BLOCKS_PER_MINUTE):
        call = block if n % 2 == 0 else unblock
        assert (await call(client, token, her.id)).status_code in (201, 204)

    response = await block(client, token, her.id)

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


async def test_blocking_needs_onboarding_done(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)
    for response in (
        await block(client, token, uuid.uuid4()),
        await unblock(client, token, uuid.uuid4()),
        await client.get("/v1/blocks", headers=bearer(token)),
    ):
        assert response.status_code == 403
        assert error(response)["code"] == "ONBOARDING_INCOMPLETE"


async def test_nothing_is_queued_or_published_for_the_blocked_person(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    published: list[events.Event],
) -> None:
    """A block is silent (D-862): no event, no notification, to anyone."""
    me, token = await make_user()
    her, _ = await make_user(Gender.FEMALE)
    both = (me.id, her.id)

    await blocked(client, token, both[1])
    await unblocked(client, token, both[1])

    assert published == []
    written = select(func.count()).where(Notification.user_id.in_(both))
    assert await db.scalar(written) == 0
