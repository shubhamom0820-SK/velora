"""`GET /v1/usernames/{u}/available` and `PUT /v1/me/username` (T-3.7): the
format, the reserved list (D-068), stored in lowercase, `USERNAME_TAKEN` in a
race, and no change once onboarding is done."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep
from app.core.errors import AppError
from app.core.security import normalize_phone
from app.modules.profiles import rules, service
from app.modules.profiles.models import Profile
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _available(client: AsyncClient, token: str, name: str) -> Response:
    return await client.get(f"/v1/usernames/{name}/available", headers=_bearer(token))


async def _put(client: AsyncClient, token: str, name: str) -> Response:
    return await client.put(
        "/v1/me/username", json={"username": name}, headers=_bearer(token)
    )


async def _at(
    db: AsyncSession, make_user: MakeUser, step: OnboardingStep
) -> tuple[User, str, Profile]:
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    user.onboarding_step = step
    profile = await db.get(Profile, user.id)
    assert profile is not None
    if step is not OnboardingStep.DONE:
        profile.username = None
    await db.flush()
    return user, token, profile


async def _someone_has(db: AsyncSession, make_user: MakeUser, name: str) -> None:
    other, _ = await make_user()
    profile = await db.get(Profile, other.id)
    assert profile is not None
    profile.username = name
    await db.flush()


# --- Availability ----------------------------------------------------------------------


async def test_a_free_name_is_available_in_whatever_case_it_is_typed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _available(client, token, "Simran.K")

    assert response.status_code == 200
    assert response.json() == {"available": True, "suggestion": None}


@pytest.mark.parametrize(
    "name", ["admin", "Ad.Min", "a.p.i", "_support_", "velora", "Ve.Lo_Ra"]
)
async def test_a_reserved_name_its_dotted_variants_and_the_brand_are_unavailable(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, name: str
) -> None:
    """No suggestion: the name and two digits is the impersonation the list
    exists to stop."""
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _available(client, token, name)

    assert response.status_code == 200
    assert response.json() == {"available": False, "suggestion": None}


async def test_a_taken_name_comes_with_a_free_suggestion(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)
    await _someone_has(db, make_user, "simran")

    body = (await _available(client, token, "Simran")).json()

    assert body["available"] is False
    suggestion = body["suggestion"]
    assert suggestion[:6] == "simran" and suggestion[6:].isdigit()
    assert len(suggestion) == 8
    assert (await _available(client, token, suggestion)).json()["available"] is True


async def test_a_suggestion_already_taken_is_never_offered(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)
    await _someone_has(db, make_user, "simran")
    await _someone_has(db, make_user, "simran07")
    draws = iter([7, 42])
    monkeypatch.setattr(secrets, "randbelow", lambda _n: next(draws))

    body = (await _available(client, token, "simran")).json()

    assert body == {"available": False, "suggestion": "simran42"}


async def test_a_suggestion_for_a_long_name_still_fits_twenty_characters(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)
    await _someone_has(db, make_user, "a" * 20)

    suggestion = (await _available(client, token, "a" * 20)).json()["suggestion"]

    assert suggestion[:18] == "a" * 18 and len(suggestion) == 20
    assert rules.username_problem(suggestion) is None


async def test_your_own_name_is_available_to_you(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.ABOUT)
    profile.username = "simran"
    await db.flush()

    response = await _available(client, token, "SIMRAN")

    assert response.json() == {"available": True, "suggestion": None}


@pytest.mark.parametrize("name", ["sim", "a" * 21, "simran k", "simran-k", "सिमरन"])
async def test_a_name_outside_the_format_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, name: str
) -> None:
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _available(client, token, name)

    assert response.status_code == 400
    assert _error(response)["details"]["fields"] == [
        {"field": "username", "problem": "must be 4 to 20 of a-z, 0-9, '.' and '_'"}
    ]


async def test_checks_are_limited_to_30_a_minute_per_user(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    _, token, _ = await _at(db, make_user, OnboardingStep.USERNAME)
    _, other_token, _ = await _at(db, make_user, OnboardingStep.USERNAME)

    allowed = [
        (await _available(client, token, f"simran{i:02d}")).status_code
        for i in range(30)
    ]
    refused = await _available(client, token, "simran30")
    someone_else = await _available(client, other_token, "simran31")

    assert allowed == [200] * 30
    assert refused.status_code == 429
    assert _error(refused)["code"] == "RATE_LIMITED"
    assert someone_else.status_code == 200


# --- Setting it ------------------------------------------------------------------------


async def test_a_username_is_stored_in_lowercase_and_moves_on_to_about(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token, profile = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, "Simran.K_99")

    assert response.status_code == 200, response.text
    assert response.json()["profile"]["username"] == "simran.k_99"
    assert response.json()["onboarding_step"] == "about"
    await db.refresh(profile)
    await db.refresh(user)
    assert profile.username == "simran.k_99"
    assert user.onboarding_step is OnboardingStep.ABOUT


@pytest.mark.parametrize("step", [OnboardingStep.ABOUT, OnboardingStep.SELFIE])
async def test_after_its_step_a_username_changes_without_advancing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token, profile = await _at(db, make_user, step)
    profile.username = "simran"
    await db.flush()

    response = await _put(client, token, "simran_k")

    assert response.status_code == 200
    await db.refresh(profile)
    await db.refresh(user)
    assert profile.username == "simran_k" and user.onboarding_step is step


async def test_once_onboarding_is_done_a_username_is_immutable(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.DONE)
    before = profile.username

    response = await _put(client, token, "simran_new")

    assert response.status_code == 422
    assert _error(response)["code"] == "IMMUTABLE_FIELD"
    await db.refresh(profile)
    assert profile.username == before


async def test_a_username_before_its_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.PROFILE)

    response = await _put(client, token, "simran")

    assert response.status_code == 403
    assert _error(response)["details"] == {"step": "profile"}
    await db.refresh(profile)
    assert profile.username is None


@pytest.mark.parametrize("name", ["Ad.Min", "velora"])
async def test_a_reserved_name_or_the_brand_is_not_yours_to_take(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, name: str
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _put(client, token, name)

    assert response.status_code == 409
    assert _error(response)["code"] == "USERNAME_TAKEN"
    await db.refresh(profile)
    assert profile.username is None


async def test_someone_elses_name_in_any_case_is_taken(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.USERNAME)
    await _someone_has(db, make_user, "simran")

    response = await _put(client, token, "SIMRAN")

    assert response.status_code == 409
    assert _error(response)["code"] == "USERNAME_TAKEN"
    await db.refresh(profile)
    assert profile.username is None


async def test_two_people_taking_one_name_at_once_the_second_is_told_its_taken(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On two connections, as two workers would be. Each waits, once it has
    found the name free, for the other to have found it free too: so both pass
    the check, and only the unique index can tell them apart. The second to
    write gets `USERNAME_TAKEN`, never a 500. Written for real, so it cleans up
    after itself."""
    settings = make_test_settings()
    user_ids = []
    async with (
        AsyncSession(test_engine, expire_on_commit=False) as setup,
        setup.begin(),
    ):
        for _ in range(2):
            phone = normalize_phone(f"+9198{uuid.uuid4().int % 10**8:08d}")
            account = await users_service.create_account(setup, phone, settings)
            account.user.onboarding_step = OnboardingStep.USERNAME
            user_ids.append(account.user.id)
    name = f"race{uuid.uuid4().hex[:8]}"

    checked = 0
    both_checked = asyncio.Event()
    real_free = service._free

    async def free_once_both_have_checked(
        session: AsyncSession, user: User, username: str
    ) -> bool:
        nonlocal checked
        result = await real_free(session, user, username)
        checked += 1
        if checked == 2:
            both_checked.set()
        await asyncio.wait_for(both_checked.wait(), timeout=5)
        return result

    monkeypatch.setattr(service, "_free", free_once_both_have_checked)

    async def attempt(user_id: uuid.UUID) -> str:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await session.get(User, user_id)
            assert user is not None
            await session.commit()
            try:
                await service.set_username(session, user, name)
            except AppError as error:
                return error.code
            return "set"

    try:
        results = await asyncio.gather(*(attempt(u) for u in user_ids))
        async with test_engine.connect() as conn:
            holders = (
                await conn.scalars(
                    text("select user_id from profiles where username = :n"),
                    {"n": name},
                )
            ).all()
    finally:
        async with test_engine.begin() as conn:
            for table in ("notification_prefs", "wallets", "profiles"):
                await conn.execute(
                    text(f"delete from {table} where user_id = any(:u)"),
                    {"u": user_ids},
                )
            await conn.execute(
                text("delete from users where id = any(:u)"), {"u": user_ids}
            )

    assert checked == 2  # both found it free: only the index stood between them
    assert sorted(results) == ["USERNAME_TAKEN", "set"]
    assert len(holders) == 1


class _Cause(Exception):
    def __init__(self, constraint_name: str) -> None:
        super().__init__("duplicate key value violates unique constraint")
        self.constraint_name = constraint_name


class _Orig(Exception):
    def __init__(self, sqlstate: str, constraint_name: str) -> None:
        super().__init__("duplicate key value violates unique constraint")
        self.sqlstate = sqlstate
        self.__cause__ = _Cause(constraint_name)


class _Flushing:
    def __init__(self, error: IntegrityError) -> None:
        self.error = error

    async def flush(self) -> None:
        raise self.error


@pytest.mark.parametrize(
    ("sqlstate", "constraint", "mapped"),
    [
        ("23505", "uq_profiles_username", True),
        ("23505", "pk_profiles", False),
        ("23514", "uq_profiles_username", False),
    ],
)
async def test_only_the_username_indexs_violation_is_username_taken(
    sqlstate: str, constraint: str, mapped: bool
) -> None:
    error = IntegrityError("UPDATE profiles ...", {}, _Orig(sqlstate, constraint))

    if mapped:
        with pytest.raises(AppError) as taken:
            await service._flush_username(_Flushing(error))  # type: ignore[arg-type]
        assert taken.value.code == "USERNAME_TAKEN"
    else:
        with pytest.raises(IntegrityError) as passed_on:
            await service._flush_username(_Flushing(error))  # type: ignore[arg-type]
        assert passed_on.value is error
