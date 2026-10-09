"""`GET /v1/reports` (T-9.8, D-911): the reports I filed, newest first, each
with its reason, when, and whom, as a card. Never a report about me, and never
a status, whatever moderation did. Across a block, either way, the card has
the name and username alone, the same whoever blocked; an erased person is
`deleted`."""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, ReportStatus
from app.core.providers import FakeProviders
from app.modules.safety.models import Report
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.discovery.support import bearer, block, error, photo
from tests.modules.safety.support import erased, report

pytestmark = pytest.mark.usefixtures("test_redis")


async def _filed(client: AsyncClient, token: str, **params: Any) -> Response:
    return await client.get("/v1/reports", params=params, headers=bearer(token))


async def _items(client: AsyncClient, token: str) -> list[dict[str, Any]]:
    response = await _filed(client, token)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def _reported(client: AsyncClient, token: str, user: User, **body: Any) -> str:
    response = await report(client, token, user.id, **body)
    assert response.status_code == 201, response.text
    report_id: str = response.json()["id"]
    return report_id


async def _online_with_a_photo(db: AsyncSession, user: User) -> None:
    await photo(db, user, place=0, matched=True)
    user.last_active_at = clock.now()
    await db.flush()


@pytest.mark.critical
async def test_my_reports_are_listed_newest_first_and_never_one_about_me(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await make_user(Gender.FEMALE)
    first, first_token = await make_user()
    second, _ = await make_user()
    await _online_with_a_photo(db, second)
    older = await _reported(client, token, first, reason="scam")
    await db.execute(
        update(Report)
        .where(Report.reporter_id == me.id)
        .values(created_at=clock.now() - timedelta(hours=1))
    )
    newer = await _reported(client, token, second, reason="harass")
    # Someone reports me: never in my list, nor theirs as mine.
    await _reported(client, first_token, me)

    items = await _items(client, token)

    assert [item["id"] for item in items] == [newer, older]
    assert set(items[0]) == {"id", "reason", "created_at", "reported"}
    assert items[0]["reason"] == "harass"
    assert items[1]["reason"] == "scam"
    assert items[0]["reported"]["id"] == str(second.id)
    assert items[0]["reported"]["first_name"] == "Test"
    assert items[0]["reported"]["main_photo_url"] is not None
    assert items[0]["reported"]["is_online"] is True
    assert items[0]["reported"]["deleted"] is False
    assert [item["reported"]["id"] for item in await _items(client, first_token)] == [
        str(me.id)
    ]


@pytest.mark.critical
async def test_what_moderation_did_is_never_said(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """No status: an actioned report reads exactly as an open one (D-911)."""
    _, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    report_id = await _reported(client, token, him)
    before = await _items(client, token)

    await db.execute(
        update(Report)
        .where(Report.id == report_id)
        .values(status=ReportStatus.ACTIONED, action="ban", resolved_at=clock.now())
    )

    assert await _items(client, token) == before
    assert "status" not in before[0]


@pytest.mark.critical
@pytest.mark.parametrize("blocker", ["me", "them"])
async def test_across_a_block_the_card_is_the_name_alone_whoever_blocked(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, blocker: str
) -> None:
    """A block is total and silent (D-862): no photo, badge or presence across
    one, and the card is the same whoever made it, so it never tells that
    they blocked me."""
    me, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    await _online_with_a_photo(db, him)
    him_id = him.id
    await _reported(client, token, him)
    if blocker == "me":
        await block(db, me, him)
    else:
        await block(db, him, me)

    [item] = await _items(client, token)

    assert item["reported"] == {
        "id": str(him_id),
        "first_name": "Test",
        "username": item["reported"]["username"],
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": False,
    }
    assert item["reported"]["username"] is not None


async def test_an_erased_person_is_listed_as_deleted(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    _, token = await make_user(Gender.FEMALE)
    him, _ = await make_user()
    him_id = him.id
    await _reported(client, token, him)
    await erased(db, him, fake_providers.storage)

    [item] = await _items(client, token)

    assert item["reported"] == {
        "id": str(him_id),
        "first_name": None,
        "username": None,
        "main_photo_url": None,
        "shows_badge": False,
        "is_online": False,
        "deleted": True,
    }


async def test_the_list_pages_by_its_cursor_and_refuses_one_it_never_gave(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(Gender.FEMALE)
    for _n in range(3):
        him, _ = await make_user()
        await _reported(client, token, him)

    one = (await _filed(client, token, limit=2)).json()
    two = (await _filed(client, token, limit=2, cursor=one["next_cursor"])).json()

    seen = [item["id"] for item in one["items"] + two["items"]]
    assert len(seen) == len(set(seen)) == 3
    assert two["next_cursor"] is None
    for params in (
        {"cursor": base64.urlsafe_b64encode(b'["x"]').decode().rstrip("=")},
        {"limit": 0},
        {"limit": 51},
    ):
        response = await _filed(client, token, **params)
        assert response.status_code == 400, params
        assert error(response)["code"] == "VALIDATION_ERROR"


async def test_signed_out_and_unfinished_onboarding_are_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, unfinished = await make_user(onboarded=False)

    signed_out = await client.get("/v1/reports")
    early = await client.get("/v1/reports", headers=bearer(unfinished))

    assert signed_out.status_code == 401
    assert error(signed_out)["code"] == "AUTH_REQUIRED"
    assert early.status_code == 403
    assert error(early)["code"] == "ONBOARDING_INCOMPLETE"
