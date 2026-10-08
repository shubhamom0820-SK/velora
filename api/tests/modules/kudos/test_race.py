"""Two kudos to the same person at once are one kudos (T-8.5): the second is
`ALREADY_EXISTS`, never a 500 and never a second row. The pair's unique key
decides, inside the insert, so no check-then-write window exists to race.

Rows are committed for real, on two fresh men who share a committed Thread of
six messages, three from each. Everything written is taken back at the end;
nothing here writes a ledger row (06-TESTING, "Tests that commit rows").

The race is forced (concurrency-tests-must-prove-overlap): both gives have
passed every check, inside open transactions, before either inserts. Then
both insert: one writes, the other waits on the unique index until the first
commits, and finds the row there.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock
from app.core.enums import Kudos as KudosKind
from app.core.enums import MessageKind, ThreadOrigin
from app.core.errors import AppError
from app.modules.kudos import repository, service
from app.modules.kudos.models import Kudos
from app.modules.kudos.schemas import GiveKudosRequest, KudosGiven
from app.modules.messages.models import Message
from app.modules.threads.models import Thread
from app.modules.users.models import User
from tests.committed import fresh_man

COMPANY_WAIT_S = 2.0
RACE_TIMEOUT_S = 10.0


@pytest.fixture
async def pair(test_engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """(the giver, the other), who have talked. Taken back after."""
    giver = await fresh_man(test_engine)
    other = await fresh_man(test_engine)
    low, high = sorted((giver, other))
    now = clock.now()
    async with AsyncSession(test_engine) as session, session.begin():
        row = Thread(
            user_low=low,
            user_high=high,
            origin=ThreadOrigin.MATCH,
            opened_by=giver,
            expires_at=now + timedelta(hours=24),
            message_count=6,
            last_message_at=now,
        )
        session.add(row)
        await session.flush()
        thread_id = row.id
        for n in range(6):
            session.add(
                Message(
                    thread_id=thread_id,
                    sender_id=(giver, other)[n % 2],
                    kind=MessageKind.TEXT,
                    body=f"Message {n + 1}",
                    client_msg_id=uuid.uuid4(),
                )
            )
    try:
        yield giver, other
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(delete(Kudos).where(Kudos.thread_id == thread_id))
            await session.execute(delete(Message).where(Message.thread_id == thread_id))
            await session.execute(delete(Thread).where(Thread.id == thread_id))


class Race:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.at_insert: set[int] = set()
        self.company = asyncio.Event()
        self.met: list[bool] = []
        real = repository.add

        async def wait_for_company_then_insert(session: AsyncSession, **kw: Any) -> Any:
            self.at_insert.add(id(session))
            if len(self.at_insert) > 1:
                self.company.set()
            try:
                await asyncio.wait_for(self.company.wait(), timeout=COMPANY_WAIT_S)
            except TimeoutError:
                self.met.append(False)
            else:
                self.met.append(True)
            return await real(session, **kw)

        monkeypatch.setattr(repository, "add", wait_for_company_then_insert)

    async def give(
        self, engine: AsyncEngine, giver: uuid.UUID, to_id: uuid.UUID, kind: KudosKind
    ) -> KudosGiven:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, giver)
                assert user is not None
            return await service.give(
                session, user, GiveKudosRequest(to_id=to_id, kind=kind)
            )


async def test_two_kudos_at_once_are_one(
    test_engine: AsyncEngine,
    pair: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    giver, other = pair
    race = Race(monkeypatch)
    tasks = [
        asyncio.ensure_future(race.give(test_engine, giver, other, kind))
        for kind in (KudosKind.GREAT_CONVERSATION, KudosKind.REALLY_THOUGHTFUL)
    ]
    try:
        async with asyncio.timeout(RACE_TIMEOUT_S):
            results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    assert race.met == [True, True]
    given = [r for r in results if isinstance(r, KudosGiven)]
    refused = [r for r in results if isinstance(r, AppError)]
    assert len(given) == 1, results
    assert [r.code for r in refused] == ["ALREADY_EXISTS"], results
    async with AsyncSession(test_engine) as session:
        rows = await session.scalar(
            select(func.count()).select_from(Kudos).where(Kudos.from_id == giver)
        )
    assert rows == 1
