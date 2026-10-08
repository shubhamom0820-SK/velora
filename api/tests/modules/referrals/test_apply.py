"""`POST /v1/referrals/apply` (T-8.6): during onboarding only, never one's own
code, once per phone number, ever (D-691), and only a code whose owner has
finished onboarding and stands (D-693). A code is looked up, never checked for
format. An under-18 refusal takes the referral with it (D-078).

Two applies at once are on two connections, committed for real, since the
user's row lock is what makes them take turns: no ledger row is ever written
there, and their referral is taken back at the end (tests/committed.py)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep, UserStatus
from app.core.errors import AppError
from app.modules.referrals import repository, service
from app.modules.referrals.models import Referral
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.committed import fresh_man
from tests.conftest import MakeUser
from tests.modules.referrals.support import (
    APPLY,
    apply,
    at_dob,
    bearer,
    error,
    ledger,
    referral_of,
)

pytestmark = pytest.mark.usefixtures("test_redis")


@pytest.mark.critical  # T-8.6: the referral every reward rests on
async def test_a_code_applied_during_onboarding_is_recorded_and_pays_nothing_yet(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    referrer, _ = await make_user()
    referrer_id = referrer.id
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id

    response = await apply(client, token, referrer.referral_code)

    assert response.status_code == 204, response.text
    assert response.content == b""
    found = await referral_of(db, referee_id)
    assert found is not None
    assert (found["referrer_id"], found["rewarded_at"]) == (referrer_id, None)
    assert await ledger(db, referee_id) == await ledger(db, referrer_id) == []


async def test_at_the_dob_step_too(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Before `dob` is allowed: an under-18 refusal deletes it (below)."""
    referrer, _ = await make_user()
    referee, token = await at_dob(db)
    referee_id = referee.id

    assert (await apply(client, token, referrer.referral_code)).status_code == 204
    assert await referral_of(db, referee_id) is not None


@pytest.mark.parametrize("typed", ["testcode", "TestCode", "  TESTCODE "])
async def test_a_code_is_looked_up_as_typed_never_checked_for_format(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, typed: str
) -> None:
    """Case is ignored (citext) and spaces around it trimmed; `TESTCODE` holds
    an `O`, which the generated alphabet never does (T-3.3): no format check."""
    referrer, _ = await make_user()
    referrer_id = referrer.id
    referrer.referral_code = "TESTCODE"
    await db.flush()
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id

    assert (await apply(client, token, typed)).status_code == 204
    found = await referral_of(db, referee_id)
    assert found is not None and found["referrer_id"] == referrer_id


async def test_a_code_nobody_has_is_not_found_and_writes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id

    response = await apply(client, token, "NOBODY22")

    assert response.status_code == 404
    assert error(response)["code"] == "NOT_FOUND"
    assert await referral_of(db, referee_id) is None


async def test_ones_own_code_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id

    response = await apply(client, token, referee.referral_code)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert error(response)["details"] == {"why": "own_code"}
    assert await referral_of(db, referee_id) is None


async def test_once_onboarding_is_done_it_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    referrer, _ = await make_user()
    referee, token = await make_user()
    referee_id = referee.id

    response = await apply(client, token, referrer.referral_code)

    assert response.status_code == 422
    assert error(response)["code"] == "NOT_ALLOWED"
    assert error(response)["details"] == {"why": "onboarding_done"}
    assert await referral_of(db, referee_id) is None


async def test_a_second_code_is_already_exists_and_the_first_stands(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    first, _ = await make_user()
    first_id = first.id
    second, _ = await make_user()
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id
    assert (await apply(client, token, first.referral_code)).status_code == 204

    response = await apply(client, token, second.referral_code)

    assert response.status_code == 409
    assert error(response)["code"] == "ALREADY_EXISTS"
    found = await referral_of(db, referee_id)
    assert found is not None and found["referrer_id"] == first_id


# --- Whose code works (D-693) ------------------------------------------------------


@pytest.mark.parametrize(
    ("step", "status"),
    [
        (OnboardingStep.PIN, UserStatus.ACTIVE),
        (OnboardingStep.DOB, UserStatus.ACTIVE),
        (OnboardingStep.DONE, UserStatus.BANNED),
        (OnboardingStep.DONE, UserStatus.FROZEN),
        (OnboardingStep.DONE, UserStatus.DELETED),
    ],
    ids=["not done", "at dob", "banned", "frozen", "deleted"],
)
async def test_a_code_whose_owner_doesnt_stand_is_the_same_not_found(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    step: OnboardingStep,
    status: UserStatus,
) -> None:
    owner, _ = await make_user()
    owner.onboarding_step, owner.status = step, status
    await db.flush()
    referee, token = await make_user(onboarded=False)
    referee_id = referee.id

    response = await apply(client, token, owner.referral_code)

    assert response.status_code == 404
    assert response.json() == (await apply(client, token, "NOBODY22")).json()
    assert await referral_of(db, referee_id) is None


async def test_a_paused_owners_code_works(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    owner, _ = await make_user()
    owner.status = UserStatus.PAUSED
    await db.flush()
    _, token = await make_user(onboarded=False)

    assert (await apply(client, token, owner.referral_code)).status_code == 204


async def test_a_womans_code_works_and_a_woman_may_apply_one(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """Who is paid is the reward's question (D-690), never apply's."""
    owner, _ = await make_user("female")
    owner_id = owner.id
    referee, token = await make_user("female", onboarded=False)
    referee_id = referee.id

    assert (await apply(client, token, owner.referral_code)).status_code == 204
    found = await referral_of(db, referee_id)
    assert found is not None and found["referrer_id"] == owner_id


# --- The body, the token, the limit ------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [{}, {"code": ""}, {"code": "   "}, {"code": "A" * 33}, {"code": "X", "extra": 1}],
    ids=["no code", "empty", "blank", "too long", "an extra field"],
)
async def test_a_body_that_isnt_one_code_is_a_validation_error(
    client: AsyncClient, make_user: MakeUser, body: dict[str, Any]
) -> None:
    _, token = await make_user(onboarded=False)

    response = await client.post(APPLY, json=body, headers=bearer(token))

    assert response.status_code == 400
    assert error(response)["code"] == "VALIDATION_ERROR"


async def test_without_a_token_it_is_401(db: AsyncSession, client: AsyncClient) -> None:
    response = await client.post(APPLY, json={"code": "TESTMAN"})

    assert response.status_code == 401


async def test_the_eleventh_apply_in_an_hour_is_rate_limited(
    client: AsyncClient, make_user: MakeUser
) -> None:
    """10 an hour per user: a few mistyped codes, never a search for codes."""
    _, token = await make_user(onboarded=False)
    for n in range(10):
        assert (await apply(client, token, f"NOBODY{n:02d}")).status_code == 404

    response = await apply(client, token, "NOBODY99")

    assert response.status_code == 429
    assert error(response)["code"] == "RATE_LIMITED"


# --- Under 18 (D-078, P-54) -------------------------------------------------------


@pytest.mark.critical  # D-078: a minor's account goes whole, referral included
async def test_a_code_applied_then_an_under_18_date_deletes_the_referral(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    referrer, _ = await make_user()
    referrer_id = referrer.id
    referee, token = await at_dob(db)
    referee_id = referee.id
    assert (await apply(client, token, referrer.referral_code)).status_code == 204

    response = await client.post(
        "/v1/me/dob", json={"dob": "2015-01-01"}, headers=bearer(token)
    )

    assert response.status_code == 422
    assert error(response)["code"] == "UNDERAGE"
    assert await db.scalar(select(User.id).where(User.id == referee_id)) is None
    assert await referral_of(db, referee_id) is None
    # The referrer is untouched.
    assert await db.scalar(select(User.status).where(User.id == referrer_id)) is (
        UserStatus.ACTIVE
    )


# --- Two at once: the user's row lock --------------------------------------------


@pytest.mark.critical  # T-8.6 "once": two applies at once are one referral
async def test_two_applies_at_once_take_turns_and_the_second_already_exists(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forced: both are inside their transactions before either asks for the
    user's row; the first to hold it then waits for the other to reach the
    number's check, which it can't while the lock holds, and goes on alone.
    The second then sees the first's referral: `ALREADY_EXISTS`. Without the
    lock both pass the check, and the second's insert breaks the key, a 500.
    Referrals run here (D-840): the conftest's setting is in the `db`
    fixture's uncommitted transaction, which these connections can't see."""
    referrer_id = await fresh_man(test_engine)
    referee_id = await fresh_man(test_engine)
    async with (
        AsyncSession(test_engine, expire_on_commit=False) as setup,
        setup.begin(),
    ):
        await setup.execute(
            update(User)
            .where(User.id == referrer_id)
            .values(onboarding_step=OnboardingStep.DONE, status=UserStatus.ACTIVE)
        )
        code = await setup.scalar(
            select(User.referral_code).where(User.id == referrer_id)
        )
        referee = await setup.get(User, referee_id)
    assert code is not None and referee is not None

    arrived, both_arrived = 0, asyncio.Event()
    checking, company = 0, asyncio.Event()
    waited_alone: list[bool] = []
    real_lock, real_check = users_service.locked_user, repository.number_was_referred

    async def lock_once_both_arrive(session: AsyncSession, user_id: uuid.UUID) -> User:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_arrived.set()
        await asyncio.wait_for(both_arrived.wait(), 10)
        return await real_lock(session, user_id)

    async def check_then_wait(session: AsyncSession, phone_hash: str) -> bool:
        nonlocal checking
        checking += 1
        if checking > 1:
            company.set()
        try:
            await asyncio.wait_for(company.wait(), 1.0)
            waited_alone.append(False)
        except TimeoutError:
            waited_alone.append(True)
        checking -= 1
        return await real_check(session, phone_hash)

    async def running(session: AsyncSession) -> bool:
        return True

    monkeypatch.setattr(service, "_running", running)
    monkeypatch.setattr(users_service, "locked_user", lock_once_both_arrive)
    monkeypatch.setattr(repository, "number_was_referred", check_then_wait)

    async def attempt() -> Exception | None:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            try:
                await service.apply(session, referee, code)
            except Exception as refused:  # noqa: BLE001 — the test reads it
                return refused
            return None

    try:
        outcomes = await asyncio.gather(attempt(), attempt())
    finally:
        async with AsyncSession(test_engine) as cleanup, cleanup.begin():
            await cleanup.execute(
                delete(Referral).where(Referral.referee_id == referee_id)
            )

    assert waited_alone == [True, True]
    assert outcomes.count(None) == 1
    [refused] = [o for o in outcomes if o is not None]
    assert isinstance(refused, AppError) and refused.code == "ALREADY_EXISTS"


async def test_nothing_logged_names_a_code(
    client: AsyncClient, make_user: MakeUser, captured_logs: Any
) -> None:
    """A code is a key to someone's account: the line names ids only."""
    referrer, _ = await make_user()
    _, token = await make_user(onboarded=False)

    await apply(client, token, referrer.referral_code)

    assert captured_logs.events
    for line in captured_logs.events:
        assert referrer.referral_code not in str(line)
    assert any(line["event"] == "referrals.applied" for line in captured_logs.events)
