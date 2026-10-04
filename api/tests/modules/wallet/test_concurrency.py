"""Fifty wallet calls at once, on fifty connections (T-5.4; 06-TESTING's 🔒
#1 and #2; D-077's layers 1, 3 and 4 at scale). Settles P-07.

Every test asserts the overlap by what the lock decides (`races.py`): all
fifty inside open transactions before any takes the lock, and each waiting
alone at its wallet's lock. Never skipped and never marked flaky: if one
fails, stop everything.

Rows are committed for real: on fresh men, never deleted, every assertion
scoped to them (tests/committed.py).
"""

from __future__ import annotations

import asyncio
import itertools
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.enums import LedgerReason
from app.core.errors import AppError
from app.modules.wallet import repository, rules, service
from app.modules.wallet.rules import Ref, RefType
from app.modules.wallet.service import LedgerResult
from tests.committed import fresh_man
from tests.infra import SERVER_URL, TEST_DATABASE_URL
from tests.modules.wallet.races import Move, Outcome, Race, ledger_of, violated

CALLS = 50
# Fifty holders one after another: a second in all, with the lock in place.
COMPANY_WAIT_S = 0.02

# One run's fifty connections at a time, on the whole server (P-142). Every
# checkout shares one Postgres of 100 connections, and two runs' fifty at once
# don't fit: the second failed loudly, on code nobody had changed. An advisory
# lock on the server's own `postgres` database, so every run and slot sees it,
# held on a connection of its own: a run that dies frees it as it closes. Its
# first key means "a fifty's turn"; P-55's slots lock on 55.
FIFTY_LOCK = 50
FIFTY_WAIT_S = 600.0


@asynccontextmanager
async def fifty_turn() -> AsyncIterator[None]:
    """Wait for the server's one fifty-connection turn, and hold it."""
    engine = create_async_engine(
        SERVER_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as connection:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + FIFTY_WAIT_S
            while not await connection.scalar(
                text("select pg_try_advisory_lock(:lock, 0)"), {"lock": FIFTY_LOCK}
            ):
                if loop.time() >= deadline:
                    pytest.fail(
                        f"Another run held the fifty-connection turn for {FIFTY_WAIT_S:.0f} s "
                        "(P-142). Let it finish; this test never skips."
                    )
                await asyncio.sleep(0.2)
            yield
    finally:
        await engine.dispose()


@pytest.fixture
async def fifty(test_engine: AsyncEngine) -> AsyncIterator[list[AsyncConnection]]:
    """Fifty connections from an engine of exactly fifty, all open before any
    test starts, and fifty distinct backends, opened only in this run's turn
    (P-142). Postgres refusing one fails the test loudly: it never runs with
    fewer, and never skips."""
    async with fifty_turn():
        async for connections in _fifty_connections():
            yield connections


async def _fifty_connections() -> AsyncIterator[list[AsyncConnection]]:
    engine = create_async_engine(
        TEST_DATABASE_URL, pool_size=CALLS, max_overflow=0, pool_timeout=30
    )
    opened: list[AsyncConnection] = []
    try:
        results = await asyncio.gather(
            *(engine.connect() for _ in range(CALLS)), return_exceptions=True
        )
        opened = [r for r in results if isinstance(r, AsyncConnection)]
        refused = [r for r in results if not isinstance(r, AsyncConnection)]
        if refused:
            pytest.fail(
                f"Postgres opened {len(opened)} of {CALLS} connections "
                f"({type(refused[0]).__name__}: {refused[0]}). The 🔒 concurrency "
                "test needs all of them: raise max_connections or let other runs "
                "finish. It never runs with fewer, and never skips."
            )
        backends = set()
        for connection in opened:
            backends.add(await connection.scalar(text("select pg_backend_pid()")))
            await connection.rollback()
        assert len(backends) == CALLS
        yield opened
    finally:
        for connection in opened:
            await connection.close()
        await engine.dispose()


def _outcomes(outcomes: list[Outcome]) -> tuple[list[LedgerResult], list[Exception]]:
    results = [o for o in outcomes if isinstance(o, LedgerResult)]
    errors = [o for o in outcomes if not isinstance(o, LedgerResult)]
    return results, errors


def _debit(man: uuid.UUID, amount: int, reason: LedgerReason, **kwargs: Any) -> Move:
    return lambda session: service.debit(session, man, amount, reason, **kwargs)


def _credit(man: uuid.UUID, amount: int, reason: LedgerReason, **kwargs: Any) -> Move:
    return lambda session: service.credit(session, man, amount, reason, **kwargs)


# --- 🔒 #1: fifty debits on ten --------------------------------------------------------


@pytest.mark.critical  # 06-TESTING.md #1
async def test_fifty_debits_on_ten_two_apply_and_the_rest_find_it_gone(
    test_engine: AsyncEngine,
    fifty: list[AsyncConnection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    man = await fresh_man(test_engine, credits=10)
    race = Race(monkeypatch, company_wait_s=COMPANY_WAIT_S)
    moves = [
        _debit(man, 5, LedgerReason.THREAD_OPEN, ref=Ref(RefType.THREAD, uuid.uuid4()))
        for _ in range(CALLS)
    ]

    results, errors = _outcomes(await race.run_on(fifty, moves))

    race.assert_every_call_overlapped_and_waited_alone()
    assert [r.applied for r in results] == [True, True]
    assert len(errors) == CALLS - 2
    for error in errors:
        assert isinstance(error, AppError), error
        assert (error.code, error.status, error.details) == (
            "INSUFFICIENT_CREDITS",
            402,
            {"required": 5, "balance": 0},
        )
    assert await ledger_of(test_engine, man) == (3, 0, 0)


# --- 🔒 #2: one key, one entry -----------------------------------------------------------


@pytest.mark.critical  # 06-TESTING.md #2
@pytest.mark.parametrize("move", ["debit", "credit"])
async def test_one_key_fifty_times_at_once_is_one_entry(
    test_engine: AsyncEngine,
    fifty: list[AsyncConnection],
    monkeypatch: pytest.MonkeyPatch,
    move: str,
) -> None:
    """One thread opened, or one payment credited, fifty times at once: the
    first applies, and each after it finds that entry and returns it."""
    if move == "debit":
        man = await fresh_man(test_engine, credits=10)
        thread = Ref(RefType.THREAD, uuid.uuid4())
        moves = [_debit(man, 5, LedgerReason.THREAD_OPEN, ref=thread)] * CALLS
        expected = (2, 5, 5)
    else:
        man = await fresh_man(test_engine)
        payment = Ref(RefType.PAYMENT, uuid.uuid4())
        moves = [_credit(man, 25, LedgerReason.PURCHASE, ref=payment)] * CALLS
        expected = (1, 25, 25)
    race = Race(monkeypatch, company_wait_s=COMPANY_WAIT_S)

    results, errors = _outcomes(await race.run_on(fifty, moves))

    race.assert_every_call_overlapped_and_waited_alone()
    assert errors == []
    assert sorted(r.applied for r in results) == [False] * (CALLS - 1) + [True]
    assert len({r.entry.id for r in results}) == 1
    assert await ledger_of(test_engine, man) == expected


@pytest.mark.critical  # 06-TESTING.md #2: one event under two keys; D-077 layer 3
async def test_one_payment_under_fifty_keys_is_one_entry(
    test_engine: AsyncEngine,
    fifty: list[AsyncConnection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fifty code paths spelling one payment's key fifty ways (a key built
    wrong): the per-event index refuses all but the first."""
    man = await fresh_man(test_engine)
    payment = Ref(RefType.PAYMENT, uuid.uuid4())
    real_key_for = rules.key_for
    spellings = itertools.count()
    monkeypatch.setattr(
        rules,
        "key_for",
        lambda user_id, reason, event: (
            f"{real_key_for(user_id, reason, event)}:spelling-{next(spellings)}"
        ),
    )
    race = Race(monkeypatch, company_wait_s=COMPANY_WAIT_S)
    moves = [_credit(man, 25, LedgerReason.PURCHASE, ref=payment)] * CALLS

    results, errors = _outcomes(await race.run_on(fifty, moves))

    race.assert_every_call_overlapped_and_waited_alone()
    assert [r.applied for r in results] == [True]
    assert [violated(e) for e in errors] == ["uq_ledger_entries_one_per_event"] * (
        CALLS - 1
    )
    assert await ledger_of(test_engine, man) == (1, 25, 25)


@pytest.mark.critical  # D-077 layer 1, as the last line of defence
async def test_one_key_fifty_times_with_the_repeat_check_bypassed_is_one_entry(
    test_engine: AsyncEngine,
    fifty: list[AsyncConnection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unique key alone: the repeat check made blind, on `thread_reopen`,
    which the per-event index leaves out, so nothing but the key stands.

    What this proves: the unique key holds when it is the last line of
    defence. What it doesn't: that the production path is right; there the
    lock and the repeat check stand in front of it (the other tests here)."""
    man = await fresh_man(test_engine, credits=10)
    thread = Ref(RefType.THREAD, uuid.uuid4())
    moves = [
        _debit(man, 1, LedgerReason.THREAD_REOPEN, ref=thread, event="client-key-1")
    ] * CALLS
    real_entry_by_key = repository.entry_by_key

    async def blind(session: Any, key: str) -> None:
        return None

    # The lock and the repeat check catch every repeat first, so without this
    # patch the unique key could never be seen going red.
    with monkeypatch.context() as scoped:
        scoped.setattr(repository, "entry_by_key", blind)
        race = Race(scoped, company_wait_s=COMPANY_WAIT_S)
        results, errors = _outcomes(await race.run_on(fifty, moves))
    # Restored when the block ended, before any assertion or later test runs.
    assert repository.entry_by_key is real_entry_by_key

    race.assert_every_call_overlapped_and_waited_alone()
    assert [r.applied for r in results] == [True]
    assert [violated(e) for e in errors] == ["uq_ledger_entries_idempotency_key"] * (
        CALLS - 1
    )
    assert await ledger_of(test_engine, man) == (2, 9, 9)


@pytest.mark.critical  # P-19 at scale
async def test_two_men_with_one_client_key_both_apply(
    test_engine: AsyncEngine,
    fifty: list[AsyncConnection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two men, each reopening his own thread with the same client key twenty-
    five times at once: one entry each. Their wallets lock apart, so each
    call waits alone at its own man's wallet while the two men's overlap."""
    first, second = (
        await fresh_man(test_engine, credits=5),
        await fresh_man(test_engine, credits=5),
    )
    moves = [
        _debit(
            man,
            1,
            LedgerReason.THREAD_REOPEN,
            ref=Ref(RefType.THREAD, thread),
            event="client-key-1",
        )
        for man, thread in ((first, uuid.uuid4()), (second, uuid.uuid4()))
        for _ in range(CALLS // 2)
    ]
    race = Race(monkeypatch, company_wait_s=COMPANY_WAIT_S)

    results, errors = _outcomes(await race.run_on(fifty, moves))

    race.assert_every_call_overlapped_and_waited_alone()
    assert errors == []
    for man in (first, second):
        his = [r for r in results if r.entry.user_id == man]
        assert sorted(r.applied for r in his) == [False] * (CALLS // 2 - 1) + [True]
        assert len({r.entry.id for r in his}) == 1
        assert await ledger_of(test_engine, man) == (2, 4, 4)


# --- Taking turns (P-142) -----------------------------------------------------------


async def test_a_fifty_waits_while_another_run_holds_the_turn() -> None:
    """Another run's fifty holds the turn: this one doesn't start until it is
    released. Without the lock it would start at once, and two runs' fifty
    connections would not fit in the shared server."""
    loop = asyncio.get_running_loop()

    async def take_the_turn() -> float:
        async with fifty_turn():
            return loop.time()

    async with fifty_turn():  # another run's fifty, mid-test
        waiting = asyncio.create_task(take_the_turn())
        await asyncio.sleep(1.0)
        assert not waiting.done(), "it took the turn while another run held it"
        released_at = loop.time()
    started_at = await asyncio.wait_for(waiting, timeout=10)

    assert started_at >= released_at
