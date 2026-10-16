"""`POST /v1/admin/users/{id}/credits` (T-9.5, D-923): an admin's grant
(`admin_grant`) or correction (`admin_correction`), up to 1,000 Velas either
way, a man's only (D-076), each naming the audit row its call writes, under an
`Idempotency-Key`.

**The correction's ledger audit** (the founder's P-840, T-9.9's way of
reading): one call, exactly one ledger entry, with its reason, its amount and
its ref, and the wallet still the sum of its ledger.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Gender, LedgerReason
from app.core.security import normalize_phone
from app.modules.admin.models import AuditLogEntry
from app.modules.users import service as users_service
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import MakeUser, make_test_settings
from tests.modules.admin.support import ADMIN, REASON, audits, auth, error, staff

pytestmark = pytest.mark.usefixtures("test_redis")


def _path(user_id: uuid.UUID) -> str:
    return f"{ADMIN}/users/{user_id}/credits"


async def _change(
    client: AsyncClient,
    token: str,
    user_id: uuid.UUID,
    delta: int,
    key: str | None = None,
    reason: str = REASON,
) -> Response:
    return await client.post(
        _path(user_id),
        json={"delta": delta, "reason": reason},
        headers=auth(token, key or f"key-{uuid.uuid4().hex[:12]}"),
    )


async def _entries(db: AsyncSession, user_id: uuid.UUID) -> list[LedgerEntry]:
    rows = await db.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    balance = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return int(balance or 0)


async def _reconciles(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """T-9.9's rule: the balance is the sum of the ledger."""
    total = await db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.delta), 0)).where(
            LedgerEntry.user_id == user_id
        )
    )
    return await _balance(db, user_id) == int(total or 0)


async def test_a_grant_is_one_admin_grant_naming_its_audit_row(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id

    response = await _change(client, token, man_id, 10, "grant-key-001")

    assert response.status_code == 204, response.text
    [entry] = await _entries(db, man_id)
    [audit] = await audits(db, admin_id, "user.credits")
    assert (entry.reason, entry.delta, entry.balance_after) == (
        LedgerReason.ADMIN_GRANT,
        10,
        10,
    )
    assert (entry.ref_type, entry.ref_id) == ("audit_log", audit.id)
    assert entry.idempotency_key == f"{man_id}:admin_grant:grant-key-001"
    assert (audit.target_type, audit.target_id, audit.meta) == (
        "user",
        man_id,
        {"delta": 10, "reason": REASON},
    )
    assert await _balance(db, man_id) == 10


@pytest.mark.critical  # P-840: the correction arrives with its ledger audit
async def test_a_correction_is_exactly_one_admin_correction_and_the_ledger_reconciles(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user(credits=10)
    man_id = man.id

    response = await _change(client, token, man_id, -4, "correct-key-01")

    assert response.status_code == 204, response.text
    corrections = [
        e
        for e in await _entries(db, man_id)
        if e.reason is LedgerReason.ADMIN_CORRECTION
    ]
    [audit] = await audits(db, admin_id, "user.credits")
    assert [(e.delta, e.balance_after, e.ref_type, e.ref_id) for e in corrections] == [
        (-4, 6, "audit_log", audit.id)
    ]
    assert corrections[0].idempotency_key == f"{man_id}:admin_correction:correct-key-01"
    assert await _balance(db, man_id) == 6
    assert await _reconciles(db, man_id)


@pytest.mark.parametrize("delta", [10, -4])
async def test_the_same_key_again_changes_nothing_and_writes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, delta: int
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user(credits=10)
    man_id = man.id

    first = await _change(client, token, man_id, delta, "repeat-key-01")
    again = await _change(client, token, man_id, delta, "repeat-key-01")

    assert [first.status_code, again.status_code] == [204, 204]
    assert len(await _entries(db, man_id)) == 2  # make_user's grant, and this
    assert len(await audits(db, admin_id, "user.credits")) == 1
    assert await _balance(db, man_id) == 10 + delta


@pytest.mark.parametrize(("first", "second"), [(10, 11), (10, -10), (-4, 4)])
async def test_the_same_key_for_another_change_already_exists(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, first: int, second: int
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user(credits=10)
    man_id = man.id
    await _change(client, token, man_id, first, "reused-key-01")

    response = await _change(client, token, man_id, second, "reused-key-01")

    assert response.status_code == 409
    assert error(response)["code"] == "ALREADY_EXISTS"
    assert len(await audits(db, admin_id, "user.credits")) == 1
    assert await _balance(db, man_id) == 10 + first


async def test_a_correction_beyond_the_balance_is_not_allowed_and_writes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Never INSUFFICIENT_CREDITS: the web reads that as the man's own, and
    opens his store sheet."""
    admin_id, token = await staff(make_user)
    man, _ = await make_user(credits=3)
    man_id = man.id

    response = await _change(client, token, man_id, -4)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert error(response)["details"] == {"why": "balance", "balance": 3}
    assert len(await _entries(db, man_id)) == 1
    assert await audits(db, admin_id) == []


@pytest.mark.parametrize("gender", [Gender.FEMALE, None], ids=["a woman", "no gender"])
async def test_only_a_man_is_given_velas(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    gender: Gender | None,
) -> None:
    """D-076: refused before the wallet, which refuses too, as the database does."""
    admin_id, token = await staff(make_user)
    account = await users_service.create_account(
        db,
        normalize_phone(f"+9196{uuid.uuid4().int % 10**8:08d}"),
        make_test_settings(),
    )
    account.user.gender = gender
    await db.flush()
    person_id = account.user.id

    response = await _change(client, token, person_id, 5)

    assert response.status_code == 422
    assert error(response)["details"]["why"] == "not_a_man"
    assert await _entries(db, person_id) == []
    assert await audits(db, admin_id) == []


async def test_an_account_nobody_holds_is_not_found(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin_id, token = await staff(make_user)

    response = await _change(client, token, uuid.uuid4(), 5)

    assert response.status_code == 404
    assert await audits(db, admin_id) == []


@pytest.mark.parametrize(
    ("body", "headers"),
    [
        ({"delta": 0, "reason": REASON}, {"Idempotency-Key": "valid-key-01"}),
        ({"delta": 1001, "reason": REASON}, {"Idempotency-Key": "valid-key-01"}),
        ({"delta": -1001, "reason": REASON}, {"Idempotency-Key": "valid-key-01"}),
        ({"delta": "5", "reason": REASON}, {"Idempotency-Key": "valid-key-01"}),
        ({"delta": 5, "reason": "short"}, {"Idempotency-Key": "valid-key-01"}),
        ({"delta": 5, "reason": REASON}, {}),
        ({"delta": 5, "reason": REASON}, {"Idempotency-Key": "short"}),
    ],
    ids=[
        "zero",
        "over 1000",
        "under -1000",
        "a string",
        "a short reason",
        "no key",
        "a key out of shape",
    ],
)
async def test_a_request_out_of_shape_is_a_validation_error(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    body: dict[str, object],
    headers: dict[str, str],
) -> None:
    admin_id, token = await staff(make_user)
    man, _ = await make_user()
    man_id = man.id

    response = await client.post(
        _path(man_id), json=body, headers={**auth(token), **headers}
    )

    assert response.status_code == 400, response.text
    assert error(response)["code"] == "VALIDATION_ERROR"
    assert await _entries(db, man_id) == []
    assert (
        await db.scalar(
            select(func.count())
            .select_from(AuditLogEntry)
            .where(AuditLogEntry.actor_id == admin_id)
        )
        == 0
    )
