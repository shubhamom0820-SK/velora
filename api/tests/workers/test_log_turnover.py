"""`log_turnover` (D-483, T-8.1): the year's turnover, logged once a day, at
warning from ₹15 lakh and error from ₹20 lakh (P-350), never above its level
below them."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

import pytest
from arq.worker import create_worker
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentStatus
from app.core.queue import ERASE_ACCOUNTS, LOG_TURNOVER, RECONCILE_LEDGER
from app.workers import main as worker
from app.workers.tasks.log_turnover import log_turnover
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.modules.payments.support import add_payment
from tests.workers.test_delete_files import SharedSession

LAKH = 1_00_000 * 100  # paise


def _lines(captured: CapturedLogs) -> list[tuple[str, int]]:
    return [
        (event["log_level"], event["turnover_paise"])
        for event in captured.events
        if event["event"] == "payments.turnover"
    ]


async def _run(db: AsyncSession) -> str:
    await db.commit()  # as a new request finds it: the job opens its own transaction
    ctx: dict[str, Any] = {"sessionmaker": SharedSession(db)}
    return await log_turnover(ctx)


@pytest.mark.critical  # D-483: the only thing that says the threshold is near
async def test_the_line_warns_at_15_lakh_and_not_a_paisa_below(
    db: AsyncSession,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    now = clock.now()
    clock.freeze(now)
    man, _ = await make_user()
    man_id = man.id
    await add_payment(
        db, man_id, status=PaymentStatus.PAID, amount_paise=15 * LAKH - 1, paid_at=now
    )

    below = await _run(db)
    await add_payment(
        db, man_id, status=PaymentStatus.PAID, amount_paise=1, paid_at=now
    )
    at = await _run(db)

    assert (below, at) == ("info", "warning")
    assert _lines(captured_logs) == [("info", 15 * LAKH - 1), ("warning", 15 * LAKH)]


async def test_the_line_is_an_error_from_20_lakh(
    db: AsyncSession,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    now = clock.now()
    clock.freeze(now)
    man, _ = await make_user()
    man_id = man.id
    await add_payment(
        db, man_id, status=PaymentStatus.PAID, amount_paise=20 * LAKH - 1, paid_at=now
    )
    below = await _run(db)
    await add_payment(
        db, man_id, status=PaymentStatus.PAID, amount_paise=1, paid_at=now
    )
    at = await _run(db)

    assert (below, at) == ("warning", "error")
    [error] = [e for e in captured_logs.events if e.get("log_level") == "error"]
    assert "P-350" in error["note"]


async def test_last_years_sales_dont_count(
    db: AsyncSession,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    """The threshold is per financial year: a crossing last year says nothing
    about this one."""
    clock.freeze(datetime(2027, 4, 2, 6, tzinfo=UTC))
    man, _ = await make_user()
    await add_payment(
        db,
        man.id,
        status=PaymentStatus.PAID,
        amount_paise=20 * LAKH,
        paid_at=datetime(2027, 3, 31, 18, 29, tzinfo=UTC),
    )

    assert await _run(db) == "info"
    assert _lines(captured_logs) == [("info", 0)]


def test_it_runs_once_a_day_at_0900_ist() -> None:
    """03:30 UTC, in UTC whatever the machine's zone: a Mac in IST and Fly in
    UTC would otherwise run it five and a half hours apart."""
    [job] = [cron for cron in worker.CRON_JOBS if cron.name == LOG_TURNOVER]
    built = create_worker(
        worker.WorkerSettings,  # type: ignore[arg-type]
        **worker.worker_options(make_test_settings()),
    )

    assert job.name == LOG_TURNOVER
    assert (job.hour, job.minute, job.second) == (3, 30, 0)
    assert job.run_at_startup is False
    assert built.timezone is UTC
    # T-9.9's reconciliation (D-940) and T-9.6's erasure (D-500) are the others.
    assert [cron.name for cron in built.cron_jobs] == [
        RECONCILE_LEDGER,
        LOG_TURNOVER,
        ERASE_ACCOUNTS,
    ]
    scheduled = copy.copy(job)  # never the module's own: ARQ keeps its next run
    scheduled.calculate_next(datetime(2026, 10, 8, 4, tzinfo=UTC))
    assert scheduled.next_run is not None
    # ARQ adds its default 123,456 µs to every cron time: to the second, 03:30.
    assert scheduled.next_run.replace(microsecond=0) == datetime(
        2026, 10, 9, 3, 30, tzinfo=UTC
    )
