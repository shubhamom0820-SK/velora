"""`recompute_fraud` (T-9.2): every 10 minutes in the worker's own loop,
everyone with a signal in the last 7 days or a score to decay scored again,
each in a transaction of their own, page by page; a freeze's `socket.close`
published once it has committed, and Redis asked nothing else. Run on the
`db` fixture's session, so every write rolls back."""

from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from datetime import timedelta
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as core_clock
from app.core.enums import FraudBand, UserStatus
from app.modules.safety.models import FraudScore
from app.modules.users.models import User
from app.workers import main as worker
from app.workers.tasks import recompute_fraud, send_push, thread_clock
from tests.conftest import MakeUser
from tests.modules.safety.test_scoring import SPAMMER, _signalled
from tests.workers.test_thread_clock import Published, Sessions


async def _sweep(db: AsyncSession, redis: Published, **kw: Any) -> dict[str, int]:
    return await recompute_fraud.recompute_all(Sessions(db), redis, **kw)  # type: ignore[arg-type]


async def _score(db: AsyncSession, user: User) -> FraudScore | None:
    return await db.get(FraudScore, user.id, populate_existing=True)


async def test_it_scores_everyone_signalled_page_by_page_and_publishes_a_freeze(
    db: AsyncSession, make_user: MakeUser
) -> None:
    spammer, _ = await make_user()
    noisy, _ = await make_user()
    quiet, _ = await make_user()
    spammer_id = spammer.id
    await _signalled(db, spammer_id, *SPAMMER)
    await _signalled(db, noisy.id, ("message_rejected", 10))
    redis = Published()

    done = await _sweep(db, redis, batch=1)

    assert done["scored"] >= 2 and done["frozen"] >= 1
    assert (await _score(db, spammer)).band is FraudBand.FREEZE  # type: ignore[union-attr]
    assert (await _score(db, noisy)).score == 10  # type: ignore[union-attr]
    assert await _score(db, quiet) is None
    assert (
        await db.get(User, spammer_id, populate_existing=True)
    ).status is UserStatus.FROZEN  # type: ignore[union-attr]
    assert (f"user:{spammer_id}", "socket.close", {}) in redis.sent


async def test_a_score_decays_to_nothing_once_its_signals_are_a_week_old(
    db: AsyncSession, make_user: MakeUser, clock: ModuleType
) -> None:
    man, _ = await make_user()
    await _signalled(db, man.id, ("message_rejected", 10))
    await _sweep(db, Published())
    assert (await _score(db, man)).score == 10  # type: ignore[union-attr]

    clock.freeze(core_clock.now() + timedelta(days=7, minutes=1))
    await _sweep(db, Published())

    row = await _score(db, man)
    assert row is not None
    assert (row.score, row.band, row.signals) == (0, FraudBand.NORMAL, {})


def test_it_runs_every_ten_minutes() -> None:
    assert recompute_fraud.EVERY_S == 600


async def test_the_worker_starts_the_fraud_loop_and_stops_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = asyncio.Event()
    seen: list[MutableMapping[str, Any]] = []

    async def fraud_run(ctx: MutableMapping[str, Any]) -> dict[str, int]:
        seen.append(ctx)
        ran.set()
        return {"scored": 0, "frozen": 0}

    async def idle_run(_ctx: MutableMapping[str, Any]) -> dict[str, int]:
        return {}

    class Idle:
        async def run(self) -> None:
            await asyncio.Event().wait()

    async def no_resources(*_: Any) -> None:
        return None

    monkeypatch.setattr(recompute_fraud, "run", fraud_run)
    monkeypatch.setattr(thread_clock, "run", idle_run)
    monkeypatch.setattr(send_push, "run", idle_run)
    monkeypatch.setattr(worker, "open_resources", no_resources)
    monkeypatch.setattr(worker, "build_providers", lambda _: None)
    monkeypatch.setattr(worker, "listen_for_wakes", lambda *_: Idle())
    monkeypatch.setattr(worker, "listen_for_pushes", lambda *_: Idle())
    ctx: dict[str, Any] = {}

    await worker.startup(ctx)
    try:
        async with asyncio.timeout(5):
            await ran.wait()
    finally:
        await worker.shutdown(ctx)

    assert seen == [ctx]
    assert ctx["fraud"].cancelled()
