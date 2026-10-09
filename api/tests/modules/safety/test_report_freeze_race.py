"""Two reports at once (T-9.2, D-901): with one report already against him,
the second and third arriving together still freeze him, once. Each report
locks the person reported before it counts, so the later one waits for the
earlier and counts it; without the lock each would count two and neither
would freeze.

Rows are committed for real, on two connections, and taken back at the end:
the reports, his signals and score, the Threads, his status. The audit log is
append-only, so its writes are recorded in memory instead, never committed;
nothing here touches a wallet. The overlap is forced and proved
(concurrency-tests-must-prove-overlap): the second report is seen waiting on
the first's lock by Postgres itself (`pg_blocking_pids`) before the first lets
go.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import ReportReason, UserStatus
from app.core.queue import FakeQueue
from app.modules.admin import service as admin_service
from app.modules.safety import repository as safety_repository
from app.modules.safety import schemas
from app.modules.safety import service as safety_service
from app.modules.safety.models import FraudEvent, FraudScore, Report
from app.modules.threads.models import Thread
from app.modules.users.models import User
from tests.committed import fresh_man
from tests.modules.album.test_race import _committed_woman
from tests.modules.threads.test_clear_race import _blocked, _pid

RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def reported(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, list[uuid.UUID]]]:
    """(him, three women each sharing a Thread with him), the first of whom
    has reported him already. Everything about him is taken back after."""
    him = await fresh_man(test_engine)
    women = [await _committed_woman(test_engine) for _ in range(3)]
    async with AsyncSession(test_engine) as session, session.begin():
        for woman in women:
            low, high = sorted((him, woman))
            session.add(
                Thread(user_low=low, user_high=high, origin="dm", opened_by=woman)
            )
        session.add(Report(reporter_id=women[0], reported_id=him, reason="harass"))
    try:
        yield him, women
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(delete(Report).where(Report.reported_id == him))
            await session.execute(delete(FraudEvent).where(FraudEvent.user_id == him))
            await session.execute(delete(FraudScore).where(FraudScore.user_id == him))
            await session.execute(
                delete(Thread).where(
                    or_(Thread.user_low == him, Thread.user_high == him)
                )
            )
            await session.execute(
                update(User).where(User.id == him).values(status=UserStatus.ACTIVE)
            )


async def _report(engine: AsyncEngine, reporter: uuid.UUID, him: uuid.UUID) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            user = await session.get(User, reporter)
        assert user is not None
        return await safety_service.report(
            session,
            user,
            schemas.FileReportRequest(
                reported_id=him, reason=ReportReason.HARASS, also_block=False
            ),
            queue=FakeQueue(),
        )


async def test_two_reports_at_once_are_counted_one_after_the_other(
    test_engine: AsyncEngine,
    reported: tuple[uuid.UUID, list[uuid.UUID]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    him, (_, second, third) = reported
    audited: list[tuple[uuid.UUID, str]] = []
    holding, release = asyncio.Event(), asyncio.Event()
    waiting: list[int] = []
    real_lock = safety_repository.lock_user

    async def audit(
        _session: AsyncSession, actor: uuid.UUID, action: str, *_: Any, **__: Any
    ) -> None:
        audited.append((actor, action))

    async def lock_user(session: AsyncSession, user_id: uuid.UUID, **kw: Any) -> Any:
        if user_id != him:
            return await real_lock(session, user_id, **kw)
        if not holding.is_set():
            found = await real_lock(session, user_id, **kw)
            holding.set()
            await release.wait()
            return found
        waiting.append(await _pid(session))
        return await real_lock(session, user_id, **kw)

    monkeypatch.setattr(admin_service, "audit", audit)
    monkeypatch.setattr(safety_repository, "lock_user", lock_user)

    first_task = asyncio.ensure_future(_report(test_engine, second, him))
    second_task: asyncio.Future[Any] | None = None
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            await holding.wait()
            second_task = asyncio.ensure_future(_report(test_engine, third, him))
            while not waiting:
                await asyncio.sleep(0.01)
            await _blocked(test_engine, waiting[0])
            release.set()
            await asyncio.gather(first_task, second_task)
    finally:
        release.set()
        for task in (first_task, second_task):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(t for t in (first_task, second_task) if t is not None),
            return_exceptions=True,
        )

    async with AsyncSession(test_engine) as session:
        status = await session.scalar(select(User.status).where(User.id == him))
    assert status is UserStatus.FROZEN
    assert [action for _, action in audited].count("fraud.freeze") == 1
