"""`GET /v1/wallet` and `GET /v1/wallet/ledger` (T-5.3, D-270).

Every entry a test writes in its own transaction shares one `created_at`, the
transaction's start (03-SCHEMA's default, `now()`). So the order these tests
expect is the rule, `(created_at, id)` newest first, computed from the rows,
never the order they were written: among entries of one transaction the order
is stable but arbitrary (T-5.3). Only the last test, whose entries commit in
three transactions of their own, sees `created_at` decide.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import LedgerReason
from app.core.pagination import PageParams
from app.modules.wallet import service
from app.modules.wallet.models import LedgerEntry
from app.modules.wallet.rules import Ref, RefType
from tests.committed import fresh_man
from tests.conftest import MakeUser
from tests.grants import grant

FIELDS = {"id", "delta", "balance_after", "reason", "created_at"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _grant(db: AsyncSession, user_id: uuid.UUID, amount: int) -> None:
    await grant(db, user_id, amount, event=f"grant-{uuid.uuid4()}")


async def _spend(db: AsyncSession, user_id: uuid.UUID, amount: int) -> Ref:
    ref = Ref(RefType.USER, uuid.uuid4())
    await service.debit(db, user_id, amount, LedgerReason.SUPER_LIKE, ref=ref)
    return ref


async def _rule_order(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """The user's entry ids as the rule orders them, sorted here in Python:
    Postgres compares uuids byte by byte, as Python compares their ints."""
    entries = (
        await db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user_id))
    ).all()
    newest_first = sorted(entries, key=lambda e: (e.created_at, e.id), reverse=True)
    return [str(e.id) for e in newest_first]


async def _all_pages(
    client: AsyncClient, token: str, limit: int
) -> tuple[list[list[str]], list[str | None]]:
    """Every page, following the cursors: each page's ids, and each cursor."""
    pages: list[list[str]] = []
    cursors: list[str | None] = []
    params: dict[str, Any] = {"limit": limit}
    while True:
        response = await client.get(
            "/v1/wallet/ledger", params=params, headers=_auth(token)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        pages.append([item["id"] for item in body["items"]])
        cursors.append(body["next_cursor"])
        if body["next_cursor"] is None:
            return pages, cursors
        params["cursor"] = body["next_cursor"]
        assert len(pages) < 50, "the cursors never ended"


# --- The balance ------------------------------------------------------------------


async def test_a_man_reads_exactly_his_balance(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(credits=25)

    response = await client.get("/v1/wallet", headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == {"balance": 25}


async def test_the_balance_follows_his_spending(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=25)
    await _spend(db, man.id, 5)

    response = await client.get("/v1/wallet", headers=_auth(token))

    assert response.json() == {"balance": 20}


async def test_a_woman_reads_a_balance_of_0_and_an_empty_ledger_never_a_refusal(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(gender="female")

    wallet = await client.get("/v1/wallet", headers=_auth(token))
    ledger = await client.get("/v1/wallet/ledger", headers=_auth(token))

    assert wallet.status_code == 200
    assert wallet.json() == {"balance": 0}
    assert ledger.status_code == 200
    assert ledger.json() == {"items": [], "next_cursor": None}


async def test_a_man_with_no_entries_reads_an_empty_ledger(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()

    response = await client.get("/v1/wallet/ledger", headers=_auth(token))

    assert response.json() == {"items": [], "next_cursor": None}


# --- Who may read -----------------------------------------------------------------


async def test_both_need_a_signed_in_user(
    client: AsyncClient, db: AsyncSession
) -> None:
    for path in ("/v1/wallet", "/v1/wallet/ledger"):
        response = await client.get(path)

        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "AUTH_REQUIRED", path


async def test_both_need_onboarding_done(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    for path in ("/v1/wallet", "/v1/wallet/ledger"):
        response = await client.get(path, headers=_auth(token))

        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "ONBOARDING_INCOMPLETE", path
        assert response.json()["error"]["details"] == {"step": "seeking"}, path


# --- An entry, as its owner sees it -----------------------------------------------


async def test_an_entry_is_exactly_its_five_fields_never_its_ref_or_key(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=25)
    ref = await _spend(db, man.id, 5)
    entries = (
        await db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == man.id))
    ).all()

    response = await client.get("/v1/wallet/ledger", headers=_auth(token))

    items = {item["id"]: item for item in response.json()["items"]}
    assert set(items) == {str(e.id) for e in entries}
    for entry in entries:
        item = items[str(entry.id)]
        assert set(item) == FIELDS
        assert item["delta"] == entry.delta
        assert item["balance_after"] == entry.balance_after
        assert item["reason"] == entry.reason.value
        created = datetime.fromisoformat(item["created_at"])
        assert created == entry.created_at
        assert created.utcoffset() is not None
        assert entry.idempotency_key not in response.text
    assert str(ref.id) not in response.text
    for leak in ("ref_type", "ref_id", "idempotency_key", "user_id", "key"):
        assert leak not in response.text, leak


async def test_another_mans_entries_never_appear(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=25)
    other, _ = await make_user(credits=40)
    await _spend(db, other.id, 5)

    response = await client.get("/v1/wallet/ledger", headers=_auth(token))

    assert [item["id"] for item in response.json()["items"]] == await _rule_order(
        db, man.id
    )


# --- Pages and order --------------------------------------------------------------


async def test_entries_sharing_a_created_at_page_by_id_each_exactly_once(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    """Five entries from one transaction, one `created_at`, at two a page: the
    id alone tells them apart, so a cursor on `created_at` alone would skip or
    repeat them."""
    man, token = await make_user(credits=30)
    await _grant(db, man.id, 10)
    await _spend(db, man.id, 5)
    await _grant(db, man.id, 7)
    await _spend(db, man.id, 3)
    stamps = await db.scalars(
        select(LedgerEntry.created_at).where(LedgerEntry.user_id == man.id)
    )
    assert len(set(stamps)) == 1, "the test needs entries that share a created_at"

    pages, cursors = await _all_pages(client, token, limit=2)

    assert [len(page) for page in pages] == [2, 2, 1]
    assert cursors[-1] is None and None not in cursors[:-1]
    assert [id_ for page in pages for id_ in page] == await _rule_order(db, man.id)


async def test_a_last_page_that_is_exactly_full_ends_the_list(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=30)
    for amount in (1, 2, 3):
        await _grant(db, man.id, amount)

    pages, cursors = await _all_pages(client, token, limit=2)

    assert [len(page) for page in pages] == [2, 2]
    assert cursors == [cursors[0], None] and cursors[0] is not None
    assert [id_ for page in pages for id_ in page] == await _rule_order(db, man.id)


async def test_twenty_to_a_page_unless_asked(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=1)
    for amount in range(1, 21):
        await _grant(db, man.id, amount)

    first = (await client.get("/v1/wallet/ledger", headers=_auth(token))).json()
    second = (
        await client.get(
            "/v1/wallet/ledger",
            params={"cursor": first["next_cursor"]},
            headers=_auth(token),
        )
    ).json()

    assert len(first["items"]) == 20 and first["next_cursor"] is not None
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert ids == await _rule_order(db, man.id)


async def test_up_to_fifty_to_a_page(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    man, token = await make_user(credits=25)

    response = await client.get(
        "/v1/wallet/ledger", params={"limit": 50}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == await _rule_order(
        db, man.id
    )


async def test_a_limit_outside_1_to_50_is_refused_never_clamped(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(credits=25)

    for limit in (0, 51, -1, "twenty"):
        response = await client.get(
            "/v1/wallet/ledger", params={"limit": limit}, headers=_auth(token)
        )

        assert response.status_code == 400, limit
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR", limit
        assert [f["field"] for f in error["details"]["fields"]] == ["limit"], limit


async def test_a_cursor_the_api_never_gave_is_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(credits=25)

    for cursor in ("not-a-cursor", "", "x" * 257):
        response = await client.get(
            "/v1/wallet/ledger", params={"cursor": cursor}, headers=_auth(token)
        )

        assert response.status_code == 400, cursor
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR", cursor
        assert [f["field"] for f in error["details"]["fields"]] == ["cursor"], cursor


async def test_a_cursor_names_a_position_never_whose_list(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser
) -> None:
    """D-270: unsigned, because the list is always the caller's own. Another
    man's cursor, or one naming a position past everything, reads only mine."""
    man, token = await make_user(credits=25)
    await _grant(db, man.id, 10)
    other, other_token = await make_user(credits=40)
    await _grant(db, other.id, 10)
    theirs = (
        await client.get(
            "/v1/wallet/ledger", params={"limit": 1}, headers=_auth(other_token)
        )
    ).json()["next_cursor"]
    after_everything = service.LEDGER_CURSOR.encode(
        (datetime(9999, 1, 1, tzinfo=UTC), uuid.UUID(int=2**128 - 1))
    )
    mine = await _rule_order(db, man.id)
    position = service.LEDGER_CURSOR.decode(theirs)

    with_theirs = await client.get(
        "/v1/wallet/ledger", params={"cursor": theirs}, headers=_auth(token)
    )
    with_any = await client.get(
        "/v1/wallet/ledger", params={"cursor": after_everything}, headers=_auth(token)
    )

    entries = (
        await db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == man.id))
    ).all()
    before = {str(e.id) for e in entries if (e.created_at, e.id) < position}
    assert [i["id"] for i in with_theirs.json()["items"]] == [
        id_ for id_ in mine if id_ in before
    ]
    assert [i["id"] for i in with_any.json()["items"]] == mine


async def test_newest_first_across_transactions(test_engine: AsyncEngine) -> None:
    """Three entries committed in three transactions, so three `created_at`s:
    the last written comes first. Committed, so a fresh man (06-TESTING), and
    read through the service: fresh men never onboard, so the route would
    refuse him."""
    man = await fresh_man(test_engine, credits=10)
    for amount in (20, 30):
        async with AsyncSession(test_engine) as session, session.begin():
            await _grant(session, man, amount)

    async with AsyncSession(test_engine) as session:
        first = await service.ledger(session, man, PageParams(cursor=None, limit=2))
    async with AsyncSession(test_engine) as session:
        second = await service.ledger(
            session, man, PageParams(cursor=first.next_cursor, limit=2)
        )

    entries = first.items + second.items
    assert [e.delta for e in entries] == [30, 20, 10]
    assert [e.balance_after for e in entries] == [60, 30, 10]
    stamps = [e.created_at for e in entries]
    assert stamps[0] > stamps[1] > stamps[2]
    assert second.next_cursor is None


# --- The contract -----------------------------------------------------------------


def test_the_schema_names_the_page_and_every_reason(app: FastAPI) -> None:
    """T-5.5 types its words for each reason from this enum (D-033, P-26)."""
    schemas = app.openapi()["components"]["schemas"]

    page = schemas["LedgerEntryPage"]
    assert set(page["properties"]) == {"items", "next_cursor"}
    assert page["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/LedgerEntry"
    }
    entry = schemas["LedgerEntry"]
    assert set(entry["properties"]) == FIELDS
    assert set(entry["required"]) == FIELDS
    assert entry["properties"]["reason"] == {
        "$ref": "#/components/schemas/LedgerReason"
    }
    assert schemas["LedgerReason"]["enum"] == [r.value for r in LedgerReason]
    assert set(schemas["Wallet"]["properties"]) == {"balance"}
    assert not [name for name in schemas if name.startswith("Page_")]
