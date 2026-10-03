"""`fresh_man`'s numbers (tests/committed.py): a counter the database keeps, so
no two men share a number, within a run, across runs on one database, or when
made at once.

Committed for real, never deleted, and every assertion is about the men these
tests made. The race asserts what the lock decides, as `test_race.py` does
(`f543b0d`): all the men reach the lock together, and each, once it has read
its number, waits for company and records whether it waited alone.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.enums import Gender
from app.core.security import E164, decrypt_phone, normalize_phone
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests import committed
from tests.committed import FRESH_PREFIX, fresh_man
from tests.conftest import make_test_settings

MEN_AT_ONCE = 3
COMPANY_WAIT_S = 0.5
ARRIVE_WAIT_S = 5.0


async def _number(engine: AsyncEngine, user_id: UUID) -> int:
    async with AsyncSession(engine) as session:
        token = await session.scalar(select(User.phone_enc).where(User.id == user_id))
    assert token is not None
    phone = decrypt_phone(token, make_test_settings())
    assert phone.startswith(FRESH_PREFIX)
    return int(phone.removeprefix(FRESH_PREFIX))


async def test_fresh_men_take_consecutive_numbers(test_engine: AsyncEngine) -> None:
    first = await fresh_man(test_engine)
    second = await fresh_man(test_engine)

    assert await _number(test_engine, second) == await _number(test_engine, first) + 1


async def test_a_fresh_man_goes_past_every_number_the_database_holds(
    test_engine: AsyncEngine,
) -> None:
    """As a new run on a database `TEST_DATABASE_URL` kept would find it: a man
    this process never made, numbered past its own. A count kept in memory
    would restart below him, into a number an earlier run already took."""
    ours = await _number(test_engine, await fresh_man(test_engine))
    earlier_runs = ours + 1000
    settings = make_test_settings()
    async with AsyncSession(test_engine) as session, session.begin():
        account = await users_service.create_account(
            session, normalize_phone(f"{FRESH_PREFIX}{earlier_runs:08d}"), settings
        )
        account.user.gender = Gender.MALE

    after = await fresh_man(test_engine)

    assert await _number(test_engine, after) == earlier_runs + 1


async def test_men_made_at_once_are_numbered_one_at_a_time(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    arrived: list[int] = []
    all_arrived = asyncio.Event()
    arrived_at_lock: list[int] = []
    reading: set[int] = set()
    company = asyncio.Event()
    waited_alone: list[bool] = []
    real_lock, real_next = committed.lock_numbers, committed.next_fresh_number

    async def arrive_together_then_lock(session: AsyncSession) -> None:
        arrived.append(1)
        if len(arrived) == MEN_AT_ONCE:
            all_arrived.set()
        await asyncio.wait_for(all_arrived.wait(), ARRIVE_WAIT_S)
        arrived_at_lock.append(len(arrived))
        await real_lock(session)

    async def read_then_wait_for_company(
        session: AsyncSession, settings: Settings
    ) -> E164:
        number = await real_next(session, settings)
        me = id(asyncio.current_task())
        reading.add(me)
        if len(reading) > 1:
            company.set()
        try:
            await asyncio.wait_for(company.wait(), COMPANY_WAIT_S)
            waited_alone.append(False)
        except TimeoutError:
            waited_alone.append(True)
        finally:
            reading.discard(me)
        return number

    monkeypatch.setattr(committed, "lock_numbers", arrive_together_then_lock)
    monkeypatch.setattr(committed, "next_fresh_number", read_then_wait_for_company)

    made = await asyncio.gather(
        *(fresh_man(test_engine) for _ in range(MEN_AT_ONCE)), return_exceptions=True
    )

    # The overlap was forced: every man was at the lock before any took it.
    assert arrived_at_lock == [MEN_AT_ONCE] * MEN_AT_ONCE
    # What the lock decided: each read its number alone.
    assert waited_alone == [True] * MEN_AT_ONCE
    men = [man for man in made if isinstance(man, UUID)]
    assert len(men) == MEN_AT_ONCE, made
    numbers = sorted([await _number(test_engine, man) for man in men])
    assert numbers == list(range(numbers[0], numbers[0] + MEN_AT_ONCE))
