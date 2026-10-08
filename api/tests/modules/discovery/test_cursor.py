"""The feed's pages (D-270, D-491): `(as_of, score, user_id)`, so a scroll is
one ranking at the instant it began, and time passing between pages can't
bring a card back or skip one; `limit` 1 to 50, refused outside; a cursor
this list didn't write refused."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.discovery.service import FEED_CURSOR
from app.modules.wallet.service import LEDGER_CURSOR
from tests.conftest import MakeUser
from tests.modules.discovery.support import discover, error, north, person

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)


async def _pages(
    client: AsyncClient, token: str, limit: int, between: object = None
) -> list[list[str]]:
    pages, cursor = [], None
    while True:
        params: dict[str, object] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await discover(client, token, **params)
        assert response.status_code == 200, response.text
        body = response.json()
        pages.append([card["id"] for card in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages
        if callable(between):
            await between()


async def test_pages_cover_the_feed_once_in_order(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    women = [(await person(db, make_user, at=north(n)))[0] for n in range(1, 6)]

    pages = await _pages(client, token, limit=2)

    assert [len(page) for page in pages] == [2, 2, 1]
    assert [i for page in pages for i in page] == [str(w.id) for w in women]


async def test_a_last_page_exactly_full_ends_the_list(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await person(db, make_user, Gender.MALE)
    for n in range(1, 5):
        await person(db, make_user, at=north(n))

    assert [len(page) for page in await _pages(client, token, limit=2)] == [2, 2]


async def test_ties_on_score_are_paged_by_id(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Everyone at one point, never active, the same completeness: one score."""
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    women = [(await person(db, make_user, at=north(2)))[0] for _ in range(5)]

    pages = await _pages(client, token, limit=2)

    assert [i for page in pages for i in page] == sorted(str(w.id) for w in women)


async def test_time_passing_between_pages_never_repeats_or_skips_a_card(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """Four minutes between each page, while everyone's recency fades: ranked
    at the scroll's `as_of`, every card comes once. Ranked at each page's own
    time, the card ending a page would score lower on the next and come back."""
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    women = [
        (
            await person(
                db, make_user, at=north(n), last_active_at=NOON - timedelta(hours=n)
            )
        )[0]
        for n in range(1, 7)
    ]

    async def later() -> None:
        clock.advance(timedelta(minutes=4))

    pages = await _pages(client, token, limit=2, between=later)

    assert [i for page in pages for i in page] == [str(w.id) for w in women]


async def test_each_cursor_carries_the_scrolls_first_instant(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    _, token = await person(db, make_user, Gender.MALE)
    for n in range(1, 4):
        await person(db, make_user, at=north(n))
    first = (await discover(client, token, limit=1)).json()["next_cursor"]
    clock.advance(timedelta(minutes=3))
    second = (await discover(client, token, limit=1, cursor=first)).json()[
        "next_cursor"
    ]

    assert FEED_CURSOR.decode(first)[0] == NOON
    assert FEED_CURSOR.decode(second)[0] == NOON


@pytest.mark.parametrize("limit", [0, 51, -1])
async def test_a_limit_outside_1_to_50_is_refused_never_clamped(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, limit: int
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await discover(client, token, limit=limit)

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "cursor",
    [
        "not-a-cursor",
        LEDGER_CURSOR.encode((NOON, uuid4())),
        FEED_CURSOR.encode((NOON, 0.5, uuid4())) + "A",
    ],
)
async def test_a_cursor_this_list_didnt_write_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, cursor: str
) -> None:
    _, token = await person(db, make_user, Gender.MALE)

    response = await discover(client, token, cursor=cursor)

    assert response.status_code == 400
    found = error(response)
    assert found["code"] == "VALIDATION_ERROR"
    assert [f["field"] for f in found["details"]["fields"]] == ["cursor"]
