"""Aggregate turnover (D-483, P-350's companion): paid payments' amounts in the
financial year, 1 April to 31 March in IST, from `payments`, never the ledger;
read by an admin at `GET /v1/admin/turnover`, audited."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LedgerReason, PaymentStatus, Role
from app.modules.admin.models import AuditLogEntry
from app.modules.payments import rules, service
from app.modules.payments.rules import FinancialYear, TurnoverLevel
from app.modules.wallet import service as wallet_service
from tests.conftest import MakeUser
from tests.modules.payments.support import add_payment, auth

pytestmark = pytest.mark.usefixtures("test_redis")

# 00:00 IST on 1 April 2027 is 18:30 UTC on 31 March: the year's last instant
# and the next year's first, a microsecond apart.
LAST_OF_2026_27 = datetime(2027, 3, 31, 18, 29, 59, 999_999, tzinfo=UTC)
FIRST_OF_2027_28 = datetime(2027, 3, 31, 18, 30, tzinfo=UTC)
YEAR_2026 = FinancialYear(2026)
YEAR_2027 = FinancialYear(2027)


# --- The financial year ------------------------------------------------------------


def test_the_year_turns_at_midnight_in_india_not_utc() -> None:
    assert rules.financial_year_of(LAST_OF_2026_27) == YEAR_2026
    assert rules.financial_year_of(FIRST_OF_2027_28) == YEAR_2027
    assert rules.financial_year_of(datetime(2027, 1, 15, tzinfo=UTC)) == YEAR_2026
    assert rules.financial_year_of(datetime(2026, 4, 1, 12, tzinfo=UTC)) == YEAR_2026


def test_a_year_runs_1_april_to_31_march() -> None:
    assert YEAR_2026.label == "2026-27"
    assert FinancialYear(2099).label == "2099-00"
    assert YEAR_2026.starts_at == datetime(2026, 3, 31, 18, 30, tzinfo=UTC)
    assert YEAR_2026.ends_at == FIRST_OF_2027_28


@pytest.mark.critical  # D-483: a sale in the wrong year hides the threshold
async def test_payments_either_side_of_1_april_fall_in_their_own_years(
    db: AsyncSession, make_user: MakeUser
) -> None:
    man, _ = await make_user()
    await add_payment(
        db, man.id, status=PaymentStatus.PAID, amount_paise=111, paid_at=LAST_OF_2026_27
    )
    await add_payment(
        db,
        man.id,
        status=PaymentStatus.PAID,
        amount_paise=222,
        paid_at=FIRST_OF_2027_28,
    )

    async with db.begin_nested():
        before = await service.turnover(db, YEAR_2026)
        after = await service.turnover(db, YEAR_2027)

    assert (before.turnover_paise, before.paid_payments) == (111, 1)
    assert (after.turnover_paise, after.paid_payments) == (222, 1)


async def test_only_paid_payments_count(db: AsyncSession, make_user: MakeUser) -> None:
    """Razorpay's captured is our `paid`. An order never paid isn't money; a
    refunded one went back (D-483)."""
    man, _ = await make_user()
    for status in PaymentStatus:
        await add_payment(db, man.id, status=status, amount_paise=1_000)

    async with db.begin_nested():
        figure = await service.turnover(db, YEAR_2026)

    assert (figure.turnover_paise, figure.paid_payments) == (1_000, 1)


async def test_turnover_is_money_in_never_velas(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """From `payments`, never the ledger: a payment's bonus Velas, and Velas
    granted with no money at all, add nothing."""
    man, _ = await make_user(credits=500)
    paid = await add_payment(
        db, man.id, status=PaymentStatus.PAID, amount_paise=150_000
    )
    paid.bonus_credits = 6
    await wallet_service.credit(
        db, man.id, 90, LedgerReason.ADMIN_GRANT, event=f"grant-{uuid.uuid4()}"
    )
    await db.flush()

    async with db.begin_nested():
        figure = await service.turnover(db, YEAR_2026)

    assert figure.turnover_paise == 150_000


# --- The levels (D-483) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("paise", "level"),
    [
        (0, TurnoverLevel.INFO),
        (15_00_000_00 - 1, TurnoverLevel.INFO),
        (15_00_000_00, TurnoverLevel.WARNING),
        (20_00_000_00 - 1, TurnoverLevel.WARNING),
        (20_00_000_00, TurnoverLevel.ERROR),
    ],
)
def test_the_lines_level_at_15_and_20_lakh(paise: int, level: TurnoverLevel) -> None:
    assert rules.turnover_level(paise) is level


# --- GET /v1/admin/turnover ----------------------------------------------------------


async def test_an_admin_reads_this_years_turnover_and_the_read_is_audited(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    """This year is the one `now()` falls in: frozen here, so a payment made
    now is in it whatever the date the suite runs on."""
    now = clock.now()
    clock.freeze(now)
    year = rules.financial_year_of(now)
    admin, token = await make_user()
    admin.role = Role.ADMIN
    admin_id = admin.id
    man, _ = await make_user()
    await add_payment(
        db, man.id, status=PaymentStatus.PAID, amount_paise=150_000, paid_at=now
    )

    response = await client.get("/v1/admin/turnover", headers=auth(token))

    assert response.status_code == 200
    assert response.json() == {
        "financial_year": year.label,
        "starts_at": year.starts_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "ends_at": year.ends_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "turnover_paise": 150_000,
        "paid_payments": 1,
        "alert_at_paise": 15_00_000_00,
        "threshold_paise": 20_00_000_00,
    }
    [audit] = (
        await db.scalars(
            select(AuditLogEntry).where(AuditLogEntry.actor_id == admin_id)
        )
    ).all()
    assert (audit.action, audit.meta) == (
        "turnover.read",
        {"financial_year": year.label},
    )


async def test_an_admin_may_ask_for_another_year(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin, token = await make_user()
    admin.role = Role.ADMIN
    man, _ = await make_user()
    await add_payment(
        db,
        man.id,
        status=PaymentStatus.PAID,
        amount_paise=222,
        paid_at=FIRST_OF_2027_28,
    )

    response = await client.get("/v1/admin/turnover?year=2027", headers=auth(token))

    assert response.json()["financial_year"] == "2027-28"
    assert response.json()["turnover_paise"] == 222


@pytest.mark.parametrize("role", [Role.USER, Role.MODERATOR])
async def test_anyone_but_an_admin_is_forbidden(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, role: Role
) -> None:
    """The company's revenue: not a moderator's to read (D-483)."""
    user, token = await make_user()
    user.role = role
    user_id = user.id

    response = await client.get("/v1/admin/turnover", headers=auth(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    audits = (
        await db.scalars(select(AuditLogEntry).where(AuditLogEntry.actor_id == user_id))
    ).all()
    assert audits == []


async def test_a_year_before_velora_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    admin, token = await make_user()
    admin.role = Role.ADMIN

    response = await client.get("/v1/admin/turnover?year=2025", headers=auth(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_first_year_ends_where_the_next_begins() -> None:
    assert YEAR_2026.ends_at - YEAR_2026.starts_at == timedelta(days=365)
    assert YEAR_2026.ends_at == YEAR_2027.starts_at
