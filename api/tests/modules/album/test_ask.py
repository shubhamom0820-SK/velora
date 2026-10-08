"""`POST /v1/album-requests` (T-8.4): asking to see someone's private photos.
1 Vela for a man, nothing for a woman (D-231, D-098, D-002), debited with the
request (rule 5) at the price he was shown (P-56, D-600); one live request per
pair; nobody pays for an empty album; and 30 days before asking again after
she declines or revokes (D-731).

Every refusal is asserted with nothing written: no request, no ledger row, the
balance as it was."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, PhotoKind, ReviewStatus
from app.modules.album.router import ASKS_PER_MINUTE
from tests.conftest import MakeUser
from tests.modules.album.support import (
    REASK,
    album_of,
    approved_without_score,
    ask,
    asked,
    decide,
    requests_between,
    revoke,
)
from tests.modules.discovery.support import block, error, photo
from tests.modules.gifts.support import balance, ledger, set_config, token_for

pytestmark = pytest.mark.usefixtures("test_redis")

NOON = datetime(2026, 10, 9, 6, 30, tzinfo=UTC)  # 12:00 IST
DAY = timedelta(days=1)
SECOND = timedelta(seconds=1)


def _refused(response: Response, code: str, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    found = error(response)
    assert found["code"] == code
    return found


async def _nothing_written(
    db: AsyncSession, man: uuid.UUID, woman: uuid.UUID, credits: int, before: int = 0
) -> None:
    assert len(await requests_between(db, man, woman)) == before
    assert await ledger(db, man) == []
    assert await balance(db, man) == credits


# --- Asking --------------------------------------------------------------------------


@pytest.mark.critical
async def test_a_man_pays_one_vela_once_with_the_request(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """D-231: viewing private pictures is 1 Vela, debited in the request's
    transaction, its ledger row naming the request (D-077)."""
    clock.freeze(NOON)
    man, token = await make_user(credits=3)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)

    body = await asked(client, token, woman_id, shown=1)

    [row] = await requests_between(db, man_id, woman_id)
    assert body == {
        "id": str(row.id),
        "requester": body["requester"],
        "owner_id": str(woman_id),
        "status": "pending",
        "created_at": body["created_at"],
        "decided_at": None,
    }
    assert body["requester"]["id"] == str(man_id)
    assert "credits_charged" not in body
    assert datetime.fromisoformat(body["created_at"]) == NOON
    assert (row.status, row.credits_charged) == ("pending", 1)
    assert await ledger(db, man_id) == [("album_request", -1, row.id)]
    assert await balance(db, man_id) == 2


async def test_asking_again_while_it_is_live_returns_it_and_charges_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)
    first = await asked(client, token, woman_id)

    assert (await asked(client, token, woman_id))["id"] == first["id"]
    assert (await decide(client, woman_token, first["id"], True)).status_code == 200
    again = await asked(client, token, woman_id)

    assert (again["id"], again["status"]) == (first["id"], "granted")
    assert len(await requests_between(db, man_id, woman_id)) == 1
    assert len(await ledger(db, man_id)) == 1
    assert await balance(db, man_id) == 2


async def test_a_woman_asks_for_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-002: free for her. No price was shown, so the field may be absent."""
    woman, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    woman_id, man_id = woman.id, man.id
    await album_of(db, man)

    await asked(client, token, man_id, shown=None)

    [row] = await requests_between(db, woman_id, man_id)
    assert row.credits_charged == 0
    rows = await db.scalar(
        text("select count(*) from ledger_entries where user_id = :u"), {"u": woman_id}
    )
    assert rows == 0


async def test_a_woman_shown_a_price_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    woman, token = await make_user(Gender.FEMALE)
    man, _ = await make_user()
    woman_id, man_id = woman.id, man.id
    await album_of(db, man)

    found = _refused(await ask(client, token, man_id, shown=1), "PRICE_CHANGED", 409)

    assert found["details"] == {"price": 0}
    assert await requests_between(db, woman_id, man_id) == []


# --- The price shown (P-56, D-600) ---------------------------------------------------


@pytest.mark.parametrize("shown", [None, 0, 2])
async def test_a_price_he_wasnt_shown_is_refused_with_nothing_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, shown: int | None
) -> None:
    """Absent means 0, so a client that forgets the field charges nothing."""
    man, token = await make_user(credits=3)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)

    found = _refused(
        await ask(client, token, woman_id, shown=shown), "PRICE_CHANGED", 409
    )

    assert found["details"] == {"price": 1}
    await _nothing_written(db, man_id, woman_id, 3)


async def test_the_row_is_the_price_and_a_changed_row_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Rule 6: the row decides; the screen's 1 after the row moved to 3 is
    refused, and 3 shown is charged 3."""
    await db.execute(
        text("update action_prices set credits = 3 where action = 'album_request'")
    )
    man, token = await make_user(credits=5)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)

    found = _refused(await ask(client, token, woman_id, shown=1), "PRICE_CHANGED", 409)
    assert found["details"] == {"price": 3}
    await _nothing_written(db, man_id, woman_id, 5)

    await asked(client, token, woman_id, shown=3)

    [row] = await requests_between(db, man_id, woman_id)
    assert row.credits_charged == 3
    assert await ledger(db, man_id) == [("album_request", -3, row.id)]


async def test_without_the_velas_nothing_is_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=0)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)

    found = _refused(await ask(client, token, woman_id), "INSUFFICIENT_CREDITS", 402)

    assert found["details"] == {"required": 1, "balance": 0}
    await _nothing_written(db, man_id, woman_id, 0)


# --- Whom ---------------------------------------------------------------------------


async def test_nobody_himself_and_a_block_either_way_are_one_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-493: the same answer as an id nobody holds, so a block is never
    revealed."""
    man, token = await make_user(credits=3)
    woman, _ = await make_user(Gender.FEMALE)
    blocked_her, _ = await make_user(Gender.FEMALE)
    blocks_him, _ = await make_user(Gender.FEMALE)
    for owner in (woman, blocked_her, blocks_him):
        await album_of(db, owner)
    await album_of(db, man)
    await block(db, man, blocked_her)
    await block(db, blocks_him, man)
    man_id, owners = man.id, (man.id, blocked_her.id, blocks_him.id)
    expected = error(await ask(client, token, uuid.uuid4()))

    for owner_id in owners:
        assert error(await ask(client, token, owner_id)) == expected
    assert expected["code"] == "NOT_FOUND"
    assert await ledger(db, man_id) == []
    assert await balance(db, man_id) == 3


async def test_someone_who_doesnt_seek_him_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """D-550's reach, as a private message's: each wants the other's gender."""
    _man, token = await make_user(credits=3)
    other_man, _ = await make_user()
    await album_of(db, other_man)
    other_id = other_man.id

    _refused(await ask(client, token, other_id), "NOT_FOUND", 404)


# --- Nothing to see -------------------------------------------------------------------


async def test_an_empty_album_is_refused_before_anything_is_charged(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Pending, rejected and removed private photos aren't shown, nor are
    public ones; and a private photo approved before D-700 wrote scored copies
    has none, so the album never shows it either (beta: such photos stay out
    until re-uploaded)."""
    man, token = await make_user(credits=3)
    woman, _ = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await photo(db, woman, place=0)
    await photo(db, woman, kind=PhotoKind.PRIVATE, status=ReviewStatus.PENDING)
    await photo(db, woman, kind=PhotoKind.PRIVATE, status=ReviewStatus.REJECTED)
    await approved_without_score(db, woman)

    found = _refused(await ask(client, token, woman_id), "NOT_ALLOWED", 422)

    assert found["details"] == {"why": "empty_album"}
    await _nothing_written(db, man_id, woman_id, 3)


# --- Asking again (D-731) ---------------------------------------------------------------


@pytest.mark.parametrize("how", ["declined", "revoked"])
async def test_thirty_days_after_she_says_no_he_may_ask_again_not_before(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    how: str,
) -> None:
    """D-731: within `album_reask_days` (30) of her decline or revoke, refused
    with nothing charged; from day 31, asked and charged as any request."""
    clock.freeze(NOON)
    man, token = await make_user(credits=5)
    woman, woman_token = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)
    first = await asked(client, token, woman_id)
    if how == "declined":
        assert (
            await decide(client, woman_token, first["id"], False)
        ).status_code == 200
    else:
        assert (await decide(client, woman_token, first["id"], True)).status_code == 200
        clock.freeze(NOON + DAY)
        assert (
            await revoke(client, token_for(woman_id), first["id"])
        ).status_code == 204
    closed = clock.now()

    for at in (closed + SECOND, closed + 30 * DAY - SECOND):
        clock.freeze(at)
        response = await ask(client, token_for(man_id), woman_id)
        found = _refused(response, "NOT_ALLOWED", 422)
        assert found["details"] == {"why": "recently_declined"}
        assert len(await requests_between(db, man_id, woman_id)) == 1
        assert await balance(db, man_id) == 4

    clock.freeze(closed + 30 * DAY)
    again = await asked(client, token_for(man_id), woman_id)

    assert again["id"] != first["id"]
    assert again["status"] == "pending"
    assert await balance(db, man_id) == 3


async def test_the_days_are_read_fresh_from_app_config(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(NOON)
    man, token = await make_user(credits=5)
    woman, woman_token = await make_user(Gender.FEMALE)
    man_id, woman_id = man.id, woman.id
    await album_of(db, woman)
    first = await asked(client, token, woman_id)
    await decide(client, woman_token, first["id"], False)
    clock.freeze(NOON + 3 * DAY)
    _refused(await ask(client, token_for(man_id), woman_id), "NOT_ALLOWED", 422)

    await set_config(db, REASK, 2)

    await asked(client, token_for(man_id), woman_id)


async def test_her_no_to_one_man_leaves_another_free_to_ask(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _man, token = await make_user(credits=3)
    _other, other_token = await make_user(credits=3)
    woman, woman_token = await make_user(Gender.FEMALE)
    await album_of(db, woman)
    woman_id = woman.id
    first = await asked(client, token, woman_id)
    await decide(client, woman_token, first["id"], False)

    await asked(client, other_token, woman_id)


# --- The request itself -------------------------------------------------------------------


async def test_a_malformed_body_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=3)
    woman, _ = await make_user(Gender.FEMALE)
    await album_of(db, woman)
    man_id, woman_id = man.id, woman.id
    for body in (
        {"owner_id": str(woman_id), "shown_price": -1},
        {"owner_id": str(woman_id), "shown_price": 1, "credits": 0},
        {"owner_id": "nobody"},
        {},
    ):
        response = await client.post(
            "/v1/album-requests",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        _refused(response, "VALIDATION_ERROR", 400)
    assert await requests_between(db, man_id, woman_id) == []


async def test_every_endpoint_needs_a_session(
    db: AsyncSession, client: AsyncClient
) -> None:
    some = uuid.uuid4()
    for method, path in (
        ("POST", "/v1/album-requests"),
        ("GET", "/v1/album-requests/incoming"),
        ("POST", f"/v1/album-requests/{some}/decide"),
        ("POST", f"/v1/album-requests/{some}/revoke"),
        ("GET", f"/v1/users/{some}/album"),
    ):
        response = await client.request(method, path, json={})
        _refused(response, "AUTH_REQUIRED", 401)


async def test_asking_is_rate_limited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _man, token = await make_user(credits=3)
    woman, _ = await make_user(Gender.FEMALE)
    await album_of(db, woman)
    woman_id = woman.id
    for _ in range(ASKS_PER_MINUTE):
        assert (await ask(client, token, woman_id)).status_code == 200

    _refused(await ask(client, token, woman_id), "RATE_LIMITED", 429)
