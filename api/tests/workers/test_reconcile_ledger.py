"""`reconcile_ledger` (T-9.9, D-940): every balance checked against its
ledger once a day, at 03:00 UTC, each mismatch an error line, which T-9.12
forwards to the alert channel."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from arq.worker import create_worker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import RECONCILE_LEDGER
from app.workers import main as worker
from app.workers.tasks.reconcile_ledger import reconcile_ledger
from tests.conftest import CapturedLogs, MakeUser, make_test_settings
from tests.workers.test_delete_files import SharedSession


async def test_the_job_logs_a_mismatch_at_error_level(
    db: AsyncSession, make_user: MakeUser, captured_logs: CapturedLogs
) -> None:
    """Made inside the rolled-back transaction, never committed (06-TESTING)."""
    man, _ = await make_user(credits=3)
    man_id = man.id
    await db.execute(
        text("UPDATE wallets SET balance = 1 WHERE user_id = :u"), {"u": man_id}
    )
    await db.commit()  # a savepoint: the job opens its own transaction
    ctx: dict[str, Any] = {"sessionmaker": SharedSession(db)}

    count = await reconcile_ledger(ctx)

    mine = [
        (e["log_level"], e["balance"], e["ledger_sum"])
        for e in captured_logs.events
        if e["event"] == "wallet.ledger_mismatch" and e["user_id"] == str(man_id)
    ]
    assert mine == [("error", 1, 3)]
    assert count >= 1


def test_it_runs_once_a_day_at_0830_ist() -> None:
    """03:00 UTC, in UTC whatever the machine's zone, half an hour before
    `log_turnover`."""
    built = create_worker(
        worker.WorkerSettings,  # type: ignore[arg-type]
        **worker.worker_options(make_test_settings()),
    )
    [job] = [cron for cron in built.cron_jobs if cron.name == RECONCILE_LEDGER]

    assert (job.hour, job.minute, job.second) == (3, 0, 0)
    assert job.run_at_startup is False
    assert built.timezone is UTC
    scheduled = copy.copy(job)  # never the module's own: ARQ keeps its next run
    scheduled.calculate_next(datetime(2026, 10, 8, 4, tzinfo=UTC))
    assert scheduled.next_run is not None
    # ARQ adds its default 123,456 µs to every cron time: to the second, 03:00.
    assert scheduled.next_run.replace(microsecond=0) == datetime(
        2026, 10, 9, 3, 0, tzinfo=UTC
    )
