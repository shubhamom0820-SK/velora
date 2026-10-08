"""Two sends at once are one after the other (T-8.9): the second counts the
first's free send, and finds the first's key.

Rows are committed for real, on a fresh man and two committed women (a gift
needs a woman, and `fresh_man` makes men only), so the two sends run on two
connections. Their sends and her notifications are taken back at the end, the
women put back as never onboarded and the man as `fresh_man` left him, and
`gift_free_weekly_limit` as it was; nothing here writes a ledger row
(06-TESTING, "Tests that commit rows"). The users stay, as every fresh man does.

The race is forced, never trusted to `gather` (concurrency-tests-must-prove-overlap):
both sends are inside open transactions before either asks for the sender's
lock, and each, holding it, waits for the other to hold it too. With the lock
each waits alone; without it they meet, and both count the same free sends.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import Gender, OnboardingStep, Seeking
from app.core.errors import AppError
from app.modules.gifts import repository, service
from app.modules.gifts.models import GiftSend
from app.modules.gifts.schemas import SendGiftRequest
from app.modules.notifications.models import Notification
from app.modules.profiles.models import Profile
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet.models import LedgerEntry
from tests.committed import fresh_man, lock_numbers, next_fresh_number
from tests.conftest import make_test_settings

COMPANY_WAIT_S = 1.0
RACE_TIMEOUT_S = 10.0
FREE = "gift_free_weekly_limit"


async def _committed_woman(engine: AsyncEngine) -> uuid.UUID:
    """A woman, onboarded and verified, on a fresh number: as `fresh_man`, but
    a gift's recipient. Never deleted; put back to `dob` after."""
    settings = make_test_settings()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            await lock_numbers(session)
            phone = await next_fresh_number(session, settings)
            account = await users_service.create_account(session, phone, settings)
            account.user.gender = Gender.FEMALE
            account.user.dob = date(2000, 1, 1)
            account.user.is_verified = True
            account.user.onboarding_step = OnboardingStep.DONE
            account.profile.first_name = "Race"
            account.profile.seeking = Seeking.MEN
        return account.user.id


@pytest.fixture
async def people(
    test_engine: AsyncEngine,
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """(a man seeking women, two women), with one free send a week."""
    man = await fresh_man(test_engine)
    women = (await _committed_woman(test_engine), await _committed_woman(test_engine))
    async with AsyncSession(test_engine) as session, session.begin():
        limit = await session.scalar(
            text("SELECT value FROM app_config WHERE key = :k"), {"k": FREE}
        )
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.DONE)
        )
        await session.execute(
            update(Profile).where(Profile.user_id == man).values(seeking=Seeking.WOMEN)
        )
        await session.execute(
            text("UPDATE app_config SET value = '1' WHERE key = :k"), {"k": FREE}
        )
    try:
        yield man, *women
    finally:
        async with AsyncSession(test_engine) as session, session.begin():
            await session.execute(delete(GiftSend).where(GiftSend.sender_id == man))
            await session.execute(
                delete(Notification).where(Notification.user_id.in_(women))
            )
            await session.execute(
                update(Profile)
                .where(Profile.user_id.in_((man, *women)))
                .values(seeking=None)
            )
            await session.execute(
                update(User)
                .where(User.id.in_((man, *women)))
                .values(onboarding_step=OnboardingStep.DOB)
            )
            await session.execute(
                text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
                {"k": FREE, "v": str(limit)},
            )


class Race:
    """Sends at once, each in a session of its own, and what the lock decided."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.started = 0
        self.started_at_lock: list[int] = []
        self.holding: set[int] = set()
        self.company = asyncio.Event()
        self.waited_alone: list[bool] = []
        real_lock = repository.lock_sender

        async def lock_then_wait_for_company(
            session: AsyncSession, sender_id: uuid.UUID
        ) -> None:
            self.started_at_lock.append(self.started)
            await real_lock(session, sender_id)
            me = id(session)
            self.holding.add(me)
            if len(self.holding) > 1:
                self.company.set()
            try:
                await asyncio.wait_for(self.company.wait(), timeout=COMPANY_WAIT_S)
            except TimeoutError:
                self.waited_alone.append(True)
            else:
                self.waited_alone.append(False)
            self.holding.discard(me)

        monkeypatch.setattr(repository, "lock_sender", lock_then_wait_for_company)

    async def send(
        self, engine: AsyncEngine, sender: uuid.UUID, request: SendGiftRequest, key: str
    ) -> Any:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                user = await session.get(User, sender)
                assert user is not None
            self.started += 1
            # Both start before either goes on: the overlap, forced.
            while self.started < 2:
                await asyncio.sleep(0.01)
            return await service.send_gift(session, user, request, key=key)

    async def run(self, *sends: Any) -> list[Any]:
        tasks = [asyncio.ensure_future(s) for s in sends]
        try:
            async with asyncio.timeout(RACE_TIMEOUT_S):
                return await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def _sends(engine: AsyncEngine, man: uuid.UUID) -> list[GiftSend]:
    async with AsyncSession(engine) as session:
        return list(
            await session.scalars(select(GiftSend).where(GiftSend.sender_id == man))
        )


async def _gift_entries(engine: AsyncEngine, man: uuid.UUID) -> int:
    async with AsyncSession(engine) as session:
        rows = await session.scalars(
            select(LedgerEntry.id).where(
                LedgerEntry.user_id == man, LedgerEntry.reason == "gift"
            )
        )
        return len(list(rows))


async def test_two_sends_at_once_share_one_free_send(
    test_engine: AsyncEngine,
    people: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One free send left and two sends, both shown free: the first is free,
    and the second, having counted it, costs its price, so is refused at the
    price it showed (D-600). Without the lock both would be free."""
    man, one, two = people
    race = Race(monkeypatch)

    results = await race.run(
        *(
            race.send(
                test_engine,
                man,
                SendGiftRequest(recipient_id=woman, gift_id="coffee", shown_price=0),
                uuid.uuid4().hex,
            )
            for woman in (one, two)
        )
    )

    assert race.started_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    sent = [r for r in results if not isinstance(r, BaseException)]
    refused = [r for r in results if isinstance(r, BaseException)]
    assert len(sent) == 1, results
    [error] = refused
    assert isinstance(error, AppError), error
    assert (error.code, error.details) == ("PRICE_CHANGED", {"price": 5})
    assert [s.credits_charged for s in await _sends(test_engine, man)] == [0]
    assert await _gift_entries(test_engine, man) == 0


async def test_one_key_twice_at_once_is_one_send(
    test_engine: AsyncEngine,
    people: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A double tap with one key: the second finds the first's send, never
    breaks on the key's unique constraint."""
    man, one, _ = people
    race = Race(monkeypatch)
    key = uuid.uuid4().hex
    request = SendGiftRequest(recipient_id=one, gift_id="rose", shown_price=0)

    results = await race.run(
        *(race.send(test_engine, man, request, key) for _ in range(2))
    )

    assert race.started_at_lock == [2, 2]
    assert race.waited_alone == [True, True]
    assert not any(isinstance(r, BaseException) for r in results), results
    assert results[0].id == results[1].id
    assert [s.id for s in await _sends(test_engine, man)] == [results[0].id]
