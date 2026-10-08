"""`POST /v1/likes/{handle}/reveal` (T-6.7, D-542): a man pays the
`liked_you_reveal` row's price, through `pricing.charge` and so the wallet's
`debit()`, once per pair, and gets the profile; a woman pays nothing (D-002).
A handle that names no like still waiting on this viewer is `NOT_FOUND`, as
one nobody holds."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile
from app.modules.swipes.models import LikedYouReveal
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeUser
from tests.modules.discovery.support import (
    HERE,
    bearer,
    block,
    error,
    north,
    person,
    swipe,
)

pytestmark = pytest.mark.usefixtures("test_redis")

NOBODY = {"error": {"code": "NOT_FOUND", "message": "Not found."}}


async def _man(db: AsyncSession, make_user: MakeUser, credits: int) -> tuple[User, str]:
    """A man with `credits`, on the grid as `person` places one."""
    me, token = await make_user(credits=credits)
    profile = await db.get(Profile, me.id)
    assert profile is not None
    profile.location = profiles_repository.point(*HERE)
    await db.flush()
    return me, token


async def _handle(client: AsyncClient, token: str) -> str:
    response = await client.get("/v1/likes", headers=bearer(token))
    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    handle: str = item["handle"]
    return handle


async def _reveal(
    client: AsyncClient, token: str, handle: str, *, shown: int | None = 1
) -> Response:
    """The reveal, sending `shown` as the price its screen showed (P-56):
    the row's 1 unless a test changed it; None sends no body at all."""
    body = None if shown is None else {"shown_price": shown}
    return await client.post(
        f"/v1/likes/{handle}/reveal", json=body, headers=bearer(token)
    )


async def _price(db: AsyncSession, credits: int, *, active: bool = True) -> None:
    await db.execute(
        text(
            "UPDATE action_prices SET credits = :c, active = :a"
            " WHERE action = 'liked_you_reveal'"
        ),
        {"c": credits, "a": active},
    )


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    found = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def _reveals(db: AsyncSession, user_id: uuid.UUID) -> list[Any]:
    rows = await db.execute(
        select(
            LedgerEntry.reason,
            LedgerEntry.delta,
            LedgerEntry.ref_type,
            LedgerEntry.ref_id,
        )
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason == "liked_you_reveal")
        .execution_options(populate_existing=True)
    )
    return [(str(r[0]), r[1], str(r[2]), r[3]) for r in rows]


async def _reveal_rows(db: AsyncSession, viewer_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await db.scalars(
            select(LikedYouReveal.liker_id)
            .where(LikedYouReveal.viewer_id == viewer_id)
            .execution_options(populate_existing=True)
        )
    )


async def test_a_man_pays_the_rows_price_once_and_sees_who_it_was(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """The price is the row's, never a literal: set to 3 here, 3 is taken."""
    await _price(db, 3)
    me, token = await _man(db, make_user, 10)
    her, _ = await person(db, make_user, at=north(2), first_name="Zeenat")
    await swipe(db, her, me, "like")
    me_id, her_id = me.id, her.id
    handle = await _handle(client, token)

    response = await _reveal(client, token, handle, shown=3)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(her_id)
    assert response.json()["first_name"] == "Zeenat"
    assert await _balance(db, me_id) == 7
    assert await _reveals(db, me_id) == [("liked_you_reveal", -3, "user", her_id)]
    assert await _reveal_rows(db, me_id) == [her_id]
    # The list now shows her.
    listed = (await client.get("/v1/likes", headers=bearer(token))).json()["items"]
    assert listed[0]["card"]["id"] == str(her_id)


async def test_revealing_again_charges_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await _man(db, make_user, 10)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "super")
    me_id = me.id
    handle = await _handle(client, token)
    assert (await _reveal(client, token, handle)).status_code == 200

    again = await _reveal(client, token, handle)

    assert again.status_code == 200
    assert await _balance(db, me_id) == 9
    assert len(await _reveals(db, me_id)) == 1


async def test_he_cant_afford_it_is_402_and_reveals_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await _price(db, 3)
    me, token = await _man(db, make_user, 2)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")
    me_id = me.id
    handle = await _handle(client, token)

    response = await _reveal(client, token, handle, shown=3)

    assert response.status_code == 402
    assert error(response)["code"] == "INSUFFICIENT_CREDITS"
    assert await _balance(db, me_id) == 2
    assert await _reveal_rows(db, me_id) == []
    listed = (await client.get("/v1/likes", headers=bearer(token))).json()["items"]
    assert listed[0]["card"] is None


async def test_a_switched_off_reveal_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    await _price(db, 1, active=False)
    me, token = await _man(db, make_user, 5)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")
    me_id = me.id
    handle = await _handle(client, token)

    response = await _reveal(client, token, handle)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert await _reveal_rows(db, me_id) == []


async def test_a_woman_pays_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await person(db, make_user, Gender.FEMALE)
    him, _ = await person(db, make_user, Gender.MALE, at=north(1))
    await swipe(db, him, me, "like")
    me_id, him_id = me.id, him.id
    handle = await _handle(client, token)

    # Her price is 0, and so is what her screen showed.
    response = await _reveal(client, token, handle, shown=0)

    assert response.status_code == 200
    assert response.json()["id"] == str(him_id)
    # Nothing charged, of any kind: no ledger row at all (D-002).
    entries = await db.scalars(
        select(LedgerEntry.id)
        .where(LedgerEntry.user_id == me_id)
        .execution_options(populate_existing=True)
    )
    assert list(entries) == []


@pytest.mark.parametrize(
    "handle", ["0" * 32, "f" * 32, "not-a-handle", "A" * 32, "0" * 31, "0" * 33]
)
async def test_a_handle_nobody_holds_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, handle: str
) -> None:
    me, token = await _man(db, make_user, 5)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")
    me_id = me.id

    response = await _reveal(client, token, handle)

    assert (response.status_code, response.json()) == (404, NOBODY)
    assert await _balance(db, me_id) == 5


async def test_another_mans_handle_names_nothing_of_mine(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    me, token = await _man(db, make_user, 5)
    other, others = await _man(db, make_user, 5)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")
    await swipe(db, her, other, "like")
    me_id = me.id
    theirs = await _handle(client, others)

    response = await _reveal(client, token, theirs)

    assert (response.status_code, response.json()) == (404, NOBODY)
    assert await _balance(db, me_id) == 5


@pytest.mark.parametrize("change", ["blocked", "swiped", "unliked"])
async def test_a_like_no_longer_waiting_is_not_found_and_charges_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, change: str
) -> None:
    me, token = await _man(db, make_user, 5)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")
    me_id = me.id
    handle = await _handle(client, token)
    if change == "blocked":
        await block(db, her, me)
    elif change == "swiped":
        await swipe(db, me, her, "pass")
    else:
        await db.execute(
            text("DELETE FROM swipes WHERE swiper_id = :a AND target_id = :b"),
            {"a": her.id, "b": me_id},
        )

    response = await _reveal(client, token, handle)

    assert (response.status_code, response.json()) == (404, NOBODY)
    assert await _balance(db, me_id) == 5


async def test_a_reveal_needs_sign_in(db: AsyncSession, client: AsyncClient) -> None:
    assert (await client.post(f"/v1/likes/{'0' * 32}/reveal")).status_code == 401


@pytest.mark.parametrize("shown", [0, 2, None])
async def test_a_price_not_the_one_shown_is_refused_with_nothing_charged_or_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, shown: int | None
) -> None:
    """P-56, D-600: shown 0, shown stale, or nothing sent, he pays nothing and
    learns the price now; the reveal isn't written, so he can try again."""
    me, token = await _man(db, make_user, 5)
    her, _ = await person(db, make_user, at=north(1))
    await swipe(db, her, me, "like")
    me_id = me.id
    handle = await _handle(client, token)

    response = await _reveal(client, token, handle, shown=shown)

    assert response.status_code == 409, response.text
    assert error(response)["code"] == "PRICE_CHANGED"
    assert error(response)["details"] == {"price": 1}
    assert await _balance(db, me_id) == 5
    assert await _reveal_rows(db, me_id) == []
    assert (await _reveal(client, token, handle)).status_code == 200
