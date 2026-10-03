"""`GET /v1/interests` and `PUT /v1/me/interests` (T-3.8): exactly 5 different
interests from the catalogue, the set replaced in one transaction, and
D-068's step rule. The step comes after photos, so tests set it directly."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep
from app.core.errors import AppError
from app.core.security import normalize_phone
from app.modules.profiles import service
from app.modules.profiles.models import ProfileInterest
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

FIVE = [3, 9, 1, 24, 12]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _put(client: AsyncClient, token: str, interest_ids: list[Any]) -> Response:
    return await client.put(
        "/v1/me/interests", json={"interest_ids": interest_ids}, headers=_bearer(token)
    )


async def _interest_ids(db: AsyncSession, user_id: uuid.UUID) -> list[int]:
    rows = await db.scalars(
        select(ProfileInterest.interest_id)
        .where(ProfileInterest.user_id == user_id)
        .order_by(ProfileInterest.interest_id)
    )
    return list(rows)


async def _at(
    db: AsyncSession, make_user: MakeUser, step: OnboardingStep
) -> tuple[User, str, uuid.UUID]:
    """A user at `step`, their token, and their id, read now: a refused request
    rolls back and expires the loaded user."""
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    user.onboarding_step = step
    await db.flush()
    return user, token, user.id


# --- The catalogue ---------------------------------------------------------------------


async def test_interests_are_the_24_in_id_order_with_exactly_their_fields(
    db: AsyncSession, client: AsyncClient
) -> None:
    """Public: no token needed."""
    response = await client.get("/v1/interests")

    assert response.status_code == 200
    interests = response.json()
    assert [i["id"] for i in interests] == list(range(1, 25))
    assert {frozenset(i) for i in interests} == {frozenset({"id", "slug", "label"})}
    assert all(i["slug"] and i["label"] for i in interests)


# --- The interests step ----------------------------------------------------------------


async def test_five_interests_at_their_step_are_set_and_move_on_to_pin(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at(db, make_user, OnboardingStep.INTERESTS)

    response = await _put(client, token, FIVE)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "pin"
    assert response.json()["profile"]["interest_ids"] == sorted(FIVE)
    assert await _interest_ids(db, user_id) == sorted(FIVE)


async def test_interests_before_their_step_are_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, user_id = await _at(db, make_user, OnboardingStep.PHOTOS)

    response = await _put(client, token, FIVE)

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(response)["details"] == {"step": "photos"}
    assert await _interest_ids(db, user_id) == []


@pytest.mark.parametrize(
    "step", [OnboardingStep.PIN, OnboardingStep.SELFIE, OnboardingStep.DONE]
)
async def test_after_their_step_interests_are_replaced_without_advancing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token, user_id = await _at(db, make_user, step)
    db.add_all([ProfileInterest(user_id=user_id, interest_id=i) for i in FIVE])
    await db.flush()

    response = await _put(client, token, [2, 4, 6, 8, 10])

    assert response.status_code == 200
    assert response.json()["onboarding_step"] == step.value
    assert await _interest_ids(db, user_id) == [2, 4, 6, 8, 10]
    await db.refresh(user)
    assert user.onboarding_step is step


@pytest.mark.parametrize(
    ("interest_ids", "problem"),
    [
        ([1, 2, 3, 4], None),
        ([1, 2, 3, 4, 5, 6], None),
        ([1, 2, 3, 4, 4], "lists an interest twice"),
        ([1, 2, 3, 4, 25], "has an id that isn't an interest"),
        ([0, 1, 2, 3, 4], None),
        ([1, 2, 3, 4, 40000], None),
    ],
    ids=["four", "six", "twice", "unknown", "zero", "past smallint"],
)
async def test_interests_that_arent_five_from_the_catalogue_are_refused(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    interest_ids: list[int],
    problem: str | None,
) -> None:
    user, token, user_id = await _at(db, make_user, OnboardingStep.INTERESTS)
    db.add_all([ProfileInterest(user_id=user_id, interest_id=i) for i in FIVE])
    await db.flush()

    response = await _put(client, token, interest_ids)

    assert response.status_code == 400, response.text
    fields = _error(response)["details"]["fields"]
    assert fields[0]["field"].startswith("interest_ids")
    if problem is not None:
        assert fields == [{"field": "interest_ids", "problem": problem}]
    assert await _interest_ids(db, user_id) == sorted(FIVE)
    await db.refresh(user)
    assert user.onboarding_step is OnboardingStep.INTERESTS


@pytest.mark.parametrize("count", [4, 6])
async def test_the_service_itself_holds_to_exactly_five(
    db: AsyncSession, make_user: MakeUser, count: int
) -> None:
    """03-SCHEMA: enforced in the service, not only by the request's schema."""
    user, _, _ = await _at(db, make_user, OnboardingStep.INTERESTS)
    await db.commit()  # as a request starts: no transaction open

    with pytest.raises(AppError) as refused:
        await service.set_interests(db, user, list(range(1, count + 1)))

    assert refused.value.details == {
        "fields": [{"field": "interest_ids", "problem": "must be exactly 5"}]
    }


def test_the_contract_says_exactly_five(app: FastAPI) -> None:
    """The request schema is the web's contract (`make types`): it says exactly
    5, read from the OpenAPI document the types are generated from."""
    schema = app.openapi()["components"]["schemas"]["InterestsSet"]
    ids = schema["properties"]["interest_ids"]

    assert schema["required"] == ["interest_ids"]
    assert (ids["minItems"], ids["maxItems"]) == (5, 5)


async def test_two_interest_writes_at_once_take_turns(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As seeking's test (T-3.6): each waits, once it holds the user, for the
    other to hold them too, up to a second. With the row lock the first waits
    its second alone and one set replaces the other; without it both hold at
    once and the user ends with both. Written for real; cleans up."""
    settings = make_test_settings()
    phone = normalize_phone(f"+9198{uuid.uuid4().int % 10**8:08d}")
    async with (
        AsyncSession(test_engine, expire_on_commit=False) as setup,
        setup.begin(),
    ):
        account = await users_service.create_account(setup, phone, settings)
        account.user.onboarding_step = OnboardingStep.INTERESTS
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

    async def attempt(ids: list[int]) -> None:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await session.get(User, user_id)
            assert user is not None
            await session.commit()
            await service.set_interests(session, user, ids)

    try:
        await asyncio.gather(attempt([1, 2, 3, 4, 5]), attempt([6, 7, 8, 9, 10]))
        async with test_engine.connect() as conn:
            left = list(
                (
                    await conn.scalars(
                        text(
                            "select interest_id from profile_interests "
                            "where user_id = :u order by interest_id"
                        ),
                        {"u": user_id},
                    )
                ).all()
            )
    finally:
        async with test_engine.begin() as conn:
            for table in (
                "profile_interests",
                "notification_prefs",
                "wallets",
                "profiles",
            ):
                await conn.execute(
                    text(f"delete from {table} where user_id = :u"), {"u": user_id}
                )
            await conn.execute(text("delete from users where id = :u"), {"u": user_id})

    assert (held, waited_alone) == (2, 1)
    assert left in ([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])
