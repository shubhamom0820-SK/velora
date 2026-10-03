"""`GET /v1/intents` and `POST /v1/me/seeking` (T-3.6): 1 to 3 different
intents from the catalogue (D-041), the set replaced in one transaction, and
D-068's step rule."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep, Seeking
from app.core.security import normalize_phone
from app.modules.profiles import service
from app.modules.profiles.models import Profile, ProfileIntent
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _seeking(
    client: AsyncClient, token: str, seeking: str, intent_ids: list[Any]
) -> Response:
    return await client.post(
        "/v1/me/seeking",
        json={"seeking": seeking, "intent_ids": intent_ids},
        headers=_bearer(token),
    )


async def _intent_ids(db: AsyncSession, user: User) -> list[int]:
    rows = await db.scalars(
        select(ProfileIntent.intent_id)
        .where(ProfileIntent.user_id == user.id)
        .order_by(ProfileIntent.intent_id)
    )
    return list(rows)


async def _at(db: AsyncSession, user: User, step: OnboardingStep) -> None:
    user.onboarding_step = step
    await db.flush()


# --- The catalogue ----------------------------------------------------------------


async def test_intents_are_the_ten_in_id_order_with_exactly_their_fields(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await client.get("/v1/intents", headers=_bearer(token))

    assert response.status_code == 200
    intents = response.json()
    assert [i["id"] for i in intents] == list(range(1, 11))
    assert {frozenset(i) for i in intents} == {frozenset({"id", "slug", "label"})}
    assert intents[0]["slug"] == "something-serious"


async def test_intents_need_a_sign_in(db: AsyncSession, client: AsyncClient) -> None:
    response = await client.get("/v1/intents")

    assert response.status_code == 401
    assert _error(response)["code"] == "AUTH_REQUIRED"


# --- The seeking step ---------------------------------------------------------------


@pytest.mark.parametrize("seeking", ["women", "men", "everyone"])
async def test_seeking_at_its_step_is_set_and_moves_on_to_profile(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, seeking: str
) -> None:
    user, token = await make_user(onboarded=False)

    response = await _seeking(client, token, seeking, [3, 1])

    assert response.status_code == 200, response.text
    me = response.json()
    assert me["onboarding_step"] == "profile"
    assert me["profile"]["seeking"] == seeking
    assert me["profile"]["intent_ids"] == [1, 3]
    profile = await db.get(Profile, user.id)
    assert profile is not None and profile.seeking is Seeking(seeking)
    assert await _intent_ids(db, user) == [1, 3]


async def test_seeking_before_its_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user(onboarded=False)
    await _at(db, user, OnboardingStep.GENDER)

    response = await _seeking(client, token, "women", [1])

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(response)["details"] == {"step": "gender"}
    await db.refresh(user)
    assert user.onboarding_step is OnboardingStep.GENDER
    assert await _intent_ids(db, user) == []


@pytest.mark.parametrize(
    "step", [OnboardingStep.PROFILE, OnboardingStep.PIN, OnboardingStep.DONE]
)
async def test_seeking_after_its_step_is_an_edit_that_doesnt_advance(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    await _at(db, user, step)
    db.add_all([ProfileIntent(user_id=user.id, intent_id=i) for i in (1, 2, 3)])
    await db.flush()

    response = await _seeking(client, token, "everyone", [7])

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == step.value
    await db.refresh(user)
    assert user.onboarding_step is step
    assert await _intent_ids(db, user) == [7]


@pytest.mark.parametrize(
    ("intent_ids", "problem"),
    [
        ([], None),
        ([1, 2, 3, 4], None),
        ([2, 2], "lists an intent twice"),
        ([1, 11], "has an id that isn't an intent"),
        ([0], None),
        ([40000], None),
        (["one"], None),
    ],
    ids=["none", "four", "twice", "unknown", "zero", "past smallint", "not a number"],
)
async def test_intents_that_break_d041_are_refused_and_change_nothing(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    intent_ids: list[Any],
    problem: str | None,
) -> None:
    user, token = await make_user(onboarded=False)
    profile = await db.get(Profile, user.id)
    assert profile is not None
    profile.seeking = Seeking.MEN
    db.add(ProfileIntent(user_id=user.id, intent_id=5))
    await db.flush()

    response = await _seeking(client, token, "women", intent_ids)

    assert response.status_code == 400, response.text
    error = _error(response)
    assert error["code"] == "VALIDATION_ERROR"
    fields = error["details"]["fields"]
    assert fields[0]["field"].startswith("intent_ids")
    if problem is not None:
        assert fields == [{"field": "intent_ids", "problem": problem}]
    await db.refresh(user)
    await db.refresh(profile)
    assert user.onboarding_step is OnboardingStep.SEEKING
    assert profile.seeking is Seeking.MEN
    assert await _intent_ids(db, user) == [5]


async def test_a_seeking_the_prototype_doesnt_offer_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user(onboarded=False)

    response = await _seeking(client, token, "nobody", [1])

    assert response.status_code == 400
    assert _error(response)["details"]["fields"][0]["field"] == "seeking"


async def test_two_seeking_writes_at_once_take_turns(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On two connections, as two workers would be. Each waits, once it holds
    the user, for the other to hold them too, up to a second: so without the
    row lock both hold at once, both replace the set, each deleting only what
    was there before, and the user ends with both sets. With the lock the
    second can't hold the user until the first commits, so the first waits its
    whole second alone, and the second's set replaces the first's.

    What is asserted is what the lock decides, never the order the event loop
    happens to resume the two in: once the first commits, Postgres hands the
    second its row before the first's coroutine runs again, as often as not.
    Written for real, so it cleans up after itself."""
    settings = make_test_settings()
    phone = normalize_phone(f"+9198{uuid.uuid4().int % 10**8:08d}")
    async with (
        AsyncSession(test_engine, expire_on_commit=False) as setup,
        setup.begin(),
    ):
        account = await users_service.create_account(setup, phone, settings)
        account.user.onboarding_step = OnboardingStep.SEEKING
        setup.add(ProfileIntent(user_id=account.user.id, intent_id=5))
    user_id = account.user.id

    held = 0
    waited_alone = 0
    both_hold = asyncio.Event()
    real_locked_user = users_service.locked_user

    async def locked_user_once_both_hold(session: AsyncSession, uid: Any) -> User:
        nonlocal held, waited_alone
        user = await real_locked_user(session, uid)
        held += 1
        if held == 2:
            both_hold.set()
        try:
            await asyncio.wait_for(both_hold.wait(), timeout=1)
        except TimeoutError:
            waited_alone += 1
        return user

    monkeypatch.setattr(users_service, "locked_user", locked_user_once_both_hold)

    async def attempt(intent_id: int) -> None:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await session.get(User, user_id)
            assert user is not None
            await session.commit()
            await service.set_seeking(session, user, Seeking.WOMEN, [intent_id])

    try:
        await asyncio.gather(attempt(1), attempt(2))
        async with test_engine.connect() as conn:
            left = (
                await conn.scalars(
                    text(
                        "select intent_id from profile_intents where user_id = :u "
                        "order by intent_id"
                    ),
                    {"u": user_id},
                )
            ).all()
    finally:
        async with test_engine.begin() as conn:
            for table in (
                "profile_intents",
                "notification_prefs",
                "wallets",
                "profiles",
            ):
                await conn.execute(
                    text(f"delete from {table} where user_id = :u"), {"u": user_id}
                )
            await conn.execute(text("delete from users where id = :u"), {"u": user_id})

    # Both held the user, never both at once: the first waited its second
    # alone, and the second, holding it after the first committed, didn't wait.
    assert (held, waited_alone) == (2, 1)
    # One set replaced the other; without the lock the user keeps both.
    assert left in ([1], [2])
