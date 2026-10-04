"""`GET /v1/prices` (T-5.2): public, and exactly the active actions, each at its
price for a man. Tested as "only these", never "at least these": with an
inactive row present, and gifts, which are priced elsewhere, absent.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Written out, as in test_service.py: D-097 to D-099, D-231 and D-250.
PRICES = {
    "album_request": 1,
    "dm_message": 2,
    "dm_open": 8,
    "liked_you_reveal": 20,
    "super_like": 5,
    "thread_extend": 10,
    "thread_open": 5,
    "thread_reopen": 2,
    "voice_unlock": 5,
}


async def test_prices_are_public_and_exactly_the_active_actions(
    client: AsyncClient, db: AsyncSession
) -> None:
    """No token: the price list is public."""
    response = await client.get("/v1/prices")

    assert response.status_code == 200
    assert response.json() == PRICES


async def test_an_inactive_action_is_left_out_and_gifts_are_never_in(
    client: AsyncClient, db: AsyncSession
) -> None:
    await db.execute(
        text("update action_prices set active = false where action = 'super_like'")
    )
    gifts = set(await db.scalars(text("select id from gifts")))

    body = (await client.get("/v1/prices")).json()

    assert body == {action: c for action, c in PRICES.items() if action != "super_like"}
    assert gifts and not gifts & body.keys()
    assert "gift" not in body


async def test_a_changed_price_shows_at_once(
    client: AsyncClient, db: AsyncSession
) -> None:
    await db.execute(
        text("update action_prices set credits = 6 where action = 'thread_open'")
    )

    body = (await client.get("/v1/prices")).json()

    assert body == {**PRICES, "thread_open": 6}
