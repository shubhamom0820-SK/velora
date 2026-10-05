"""The PIN lock (T-3.9): `POST /auth/pin/set`, `POST /auth/pin/verify` and
`POST /me/pin/skip`. D-069's rules, its reset, the 10-minute window read from
`auth_time` (D-071), five wrong PINs revoking every session, a refused hash
that doesn't count, and what the lock doesn't do (D-067's 15-minute tail)."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from argon2 import PasswordHasher, profiles
from httpx import AsyncClient, Response
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import security
from app.core.enums import Gender, OnboardingStep, Role
from app.core.errors import AppError
from app.core.providers import FakeProviders
from app.core.security import (
    E164,
    PinCheck,
    check_pin,
    hash_phone,
    hash_pin,
    make_access_token,
    normalize_phone,
)
from app.modules.auth import service as auth_service
from app.modules.auth.models import Session
from app.modules.users import service as users_service
from app.modules.users.models import User
from seed.data import TEST_WOMAN_PIN
from tests.conftest import CapturedLogs, MakeUser, make_test_settings

pytestmark = pytest.mark.usefixtures("test_redis")

SETTINGS = make_test_settings()
START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
PIN = TEST_WOMAN_PIN
NEW_PIN = "5926"
WRONG = "3817"
PHONE = E164("+919812345611")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _set(
    client: AsyncClient, token: str, pin: Any, current_pin: Any = None
) -> Response:
    body = (
        {"pin": pin}
        if current_pin is None
        else {"pin": pin, "current_pin": current_pin}
    )
    return await client.post("/v1/auth/pin/set", json=body, headers=_bearer(token))


async def _verify(client: AsyncClient, token: str, pin: Any) -> Response:
    return await client.post(
        "/v1/auth/pin/verify", json={"pin": pin}, headers=_bearer(token)
    )


def _signed_in_at(user: User, auth_time: datetime) -> str:
    return make_access_token(user.id, Role.USER, SETTINGS, auth_time=auth_time)


async def _with_pin(db: AsyncSession, user: User, pin: str = PIN) -> str:
    """Give `user` a PIN, as set an hour ago: their token isn't fresh."""
    user.pin_hash = await hash_pin(pin, SETTINGS)
    await db.flush()
    return _signed_in_at(user, START - timedelta(hours=1))


async def _row(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    assert user is not None
    return user


async def _pin_is(db: AsyncSession, user_id: uuid.UUID, pin: str) -> bool:
    stored = (await _row(db, user_id)).pin_hash
    return (
        stored is not None and await check_pin(pin, stored, SETTINGS) is PinCheck.MATCH
    )


async def _sign_in(
    client: AsyncClient, fake_providers: FakeProviders, clock: ModuleType
) -> str:
    """A real sign-in by OTP: its access token, `auth_time` now. Moves the
    clock past the 45-second resend lock first, so it can be called again."""
    clock.advance(timedelta(seconds=46))
    typed = PHONE.removeprefix("+91")
    assert (
        await client.post("/v1/auth/otp/send", json={"phone": typed})
    ).status_code == 200
    verified = await client.post(
        "/v1/auth/otp/verify",
        json={"phone": typed, "otp": fake_providers.sms.sent[-1].code},
    )
    assert verified.status_code == 200, verified.text
    token: str = verified.json()["access_token"]
    return token


async def _account(db: AsyncSession) -> User:
    user = await db.scalar(
        select(User).where(User.phone_hash == hash_phone(PHONE, SETTINGS))
    )
    assert user is not None
    return user


# --- Setting a first PIN -----------------------------------------------------------------


async def test_a_first_pin_at_its_step_is_set_and_moves_on_to_selfie(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.PIN
    await db.flush()

    response = await _set(client, token, PIN)

    assert response.status_code == 204, response.text
    row = await _row(db, user.id)
    assert row.onboarding_step is OnboardingStep.SELFIE
    assert await _pin_is(db, user.id, PIN)
    # Stored at D-062's parameters, the only ones check_pin accepts.
    assert row.pin_hash is not None
    assert row.pin_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    me = await client.get("/v1/me", headers=_bearer(token))
    assert me.json()["has_pin"] is True


@pytest.mark.parametrize(
    ("pin", "problem"),
    [
        ("1111", "is one digit four times"),
        ("1234", "is a straight run of digits"),
        ("9876", "is a straight run of digits"),
        ("1212", "is a pair of digits, repeated"),
        ("2001", "is one of the most common PINs"),
    ],
)
async def test_a_pin_of_a_refused_shape_is_a_validation_error(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, pin: str, problem: str
) -> None:
    user, token = await make_user()

    response = await _set(client, token, pin)

    assert response.status_code == 400
    assert _error(response)["details"]["fields"] == [
        {"field": "pin", "problem": problem}
    ]
    assert (await _row(db, user.id)).pin_hash is None


@pytest.mark.parametrize("pin", ["12a4", "12345", "123", 4829, ""])
async def test_a_pin_that_isnt_four_digits_is_refused_by_the_schema(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, pin: Any
) -> None:
    user, token = await make_user()

    response = await _set(client, token, pin)

    assert response.status_code == 400
    assert _error(response)["details"]["fields"][0]["field"] == "pin"
    assert (await _row(db, user.id)).pin_hash is None


async def test_a_pin_before_its_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user(onboarded=False)
    user_id = user.id
    user.onboarding_step = OnboardingStep.INTERESTS
    await db.flush()

    response = await _set(client, token, PIN)

    assert response.status_code == 403
    assert _error(response)["details"] == {"step": "interests"}
    assert (await _row(db, user_id)).pin_hash is None


@pytest.mark.parametrize("step", [OnboardingStep.SELFIE, OnboardingStep.DONE])
async def test_after_its_step_a_first_pin_is_set_without_advancing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    user.onboarding_step = step
    await db.flush()

    response = await _set(client, token, PIN)

    assert response.status_code == 204
    row = await _row(db, user.id)
    assert row.onboarding_step is step
    assert await _pin_is(db, user.id, PIN)


# --- Changing it: the current PIN, or a sign-in under 10 minutes old (D-069, D-071) ------


@pytest.mark.parametrize(
    "signed_in_ago",
    [timedelta(0), timedelta(minutes=9, seconds=59)],
    ids=["now", "9:59"],
)
async def test_within_ten_minutes_of_signing_in_a_pin_changes_without_the_current(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    signed_in_ago: timedelta,
) -> None:
    clock.freeze(START)
    user, _ = await make_user()
    await _with_pin(db, user)
    user.pin_failed = 3
    await db.flush()

    response = await _set(client, _signed_in_at(user, START - signed_in_ago), NEW_PIN)

    assert response.status_code == 204, response.text
    assert await _pin_is(db, user.id, NEW_PIN)
    # A new PIN starts with no wrong tries against it.
    assert (await _row(db, user.id)).pin_failed == 0


@pytest.mark.parametrize(
    "signed_in_ago",
    [timedelta(minutes=10), timedelta(minutes=10, seconds=1), timedelta(days=3)],
    ids=["10:00", "10:01", "three days"],
)
async def test_ten_minutes_after_signing_in_a_pin_needs_the_current_one(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    signed_in_ago: timedelta,
) -> None:
    clock.freeze(START)
    user, _ = await make_user()
    await _with_pin(db, user)
    token = _signed_in_at(user, START - signed_in_ago)

    refused = await _set(client, token, NEW_PIN)

    assert refused.status_code == 400
    assert _error(refused)["details"]["fields"] == [
        {
            "field": "current_pin",
            "problem": "is needed to change your PIN, unless you signed in within 10 minutes",
        }
    ]
    assert await _pin_is(db, user.id, PIN)
    assert (await _row(db, user.id)).pin_failed == 0

    allowed = await _set(client, token, NEW_PIN, current_pin=PIN)

    assert allowed.status_code == 204
    assert await _pin_is(db, user.id, NEW_PIN)


async def test_a_pin_set_meanwhile_by_another_request_needs_the_current_one(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A first PIN is checked, then hashed outside any transaction, then
    written. If another request sets one in between, the write must not
    replace it without the proof a change needs."""
    clock.freeze(START)
    user, _ = await make_user()
    user_id = user.id
    token = _signed_in_at(user, START - timedelta(hours=1))
    theirs = await hash_pin(PIN, SETTINGS)
    real_hash_pin = security.hash_pin

    async def another_request_sets_one_first(pin: str, settings: Any) -> str:
        async with db.begin():
            await db.execute(
                update(User).where(User.id == user_id).values(pin_hash=theirs)
            )
        return await real_hash_pin(pin, settings)

    monkeypatch.setattr(auth_service, "hash_pin", another_request_sets_one_first)
    response = await _set(client, token, NEW_PIN)

    assert response.status_code == 400
    assert _error(response)["details"]["fields"][0]["field"] == "current_pin"
    assert await _pin_is(db, user_id, PIN)


async def test_a_wrong_current_pin_counts_as_a_wrong_pin(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    user, _ = await make_user()
    token = await _with_pin(db, user)

    response = await _set(client, token, NEW_PIN, current_pin=WRONG)

    assert response.status_code == 401
    assert _error(response) == {
        "code": "PIN_INVALID",
        "message": "That PIN isn't right.",
        "details": {"attempts_left": 4},
    }
    assert await _pin_is(db, user.id, PIN)
    assert (await _row(db, user.id)).pin_failed == 1


async def test_the_window_is_the_sign_in_never_the_refresh(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """With real tokens: fresh at 9 minutes; not at 11, though the token still
    works; a refresh then carries the sign-in's `auth_time` and stays not
    fresh (D-071); a new sign-in by OTP is fresh again: D-069's "forgot PIN"."""
    clock.freeze(START)
    signed_in = await _sign_in(client, fake_providers, clock)
    user = await _account(db)
    # A man, as only a man finishes without a matched selfie (D-310's trigger).
    user.gender = Gender.MALE
    user.onboarding_step = OnboardingStep.DONE
    await _with_pin(db, user)

    clock.advance(timedelta(minutes=9))
    assert (await _set(client, signed_in, NEW_PIN)).status_code == 204

    clock.advance(timedelta(minutes=2))
    assert (await client.get("/v1/me", headers=_bearer(signed_in))).status_code == 200
    late = await _set(client, signed_in, PIN)
    assert late.status_code == 400
    assert _error(late)["details"]["fields"][0]["field"] == "current_pin"

    cookies = {c: v for c, v in client.cookies.items()}
    refreshed = await client.post(
        "/v1/auth/refresh",
        headers={
            "Cookie": f"refresh_local={cookies['refresh_local']}; "
            f"csrf_local={cookies['csrf_local']}",
            "X-CSRF": cookies["csrf_local"],
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    after_refresh = await _set(client, refreshed.json()["access_token"], PIN)
    assert after_refresh.status_code == 400

    again = await _sign_in(client, fake_providers, clock)
    assert (await _set(client, again, PIN)).status_code == 204
    assert await _pin_is(db, user.id, PIN)


# --- Verifying it ----------------------------------------------------------------------


async def test_the_right_pin_is_204_and_clears_the_count(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, _ = await make_user()
    token = await _with_pin(db, user)
    user.pin_failed = 3
    await db.flush()

    response = await _verify(client, token, PIN)

    assert response.status_code == 204
    assert (await _row(db, user.id)).pin_failed == 0


async def test_five_wrong_pins_revoke_every_session_of_the_user(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """Every session, both devices' families, not only this one's (D-069)."""
    clock.freeze(START)
    first_device = await _sign_in(client, fake_providers, clock)
    await _sign_in(client, fake_providers, clock)
    user = await _account(db)
    user_id = user.id
    await _with_pin(db, user)
    families = await db.scalars(
        select(Session.family_id).where(Session.user_id == user_id)
    )
    assert len(set(families)) == 2

    answers = [await _verify(client, first_device, WRONG) for _ in range(5)]

    assert [_error(a)["code"] for a in answers] == ["PIN_INVALID"] * 4 + [
        "SESSION_REVOKED"
    ]
    assert [_error(a).get("details") for a in answers[:4]] == [
        {"attempts_left": n} for n in (4, 3, 2, 1)
    ]
    assert answers[4].status_code == 401
    live = await db.scalar(
        text("select count(*) from sessions where user_id = :u and revoked_at is null"),
        {"u": user_id},
    )
    assert live == 0
    assert (await _row(db, user_id)).pin_failed == 5


async def test_once_locked_even_the_right_pin_is_refused_and_not_counted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """No sixth guess: past five, nothing is checked until a fresh sign-in."""
    user, _ = await make_user()
    token = await _with_pin(db, user)
    user.pin_failed = 5
    await db.flush()

    right = await _verify(client, token, PIN)
    change = await _set(client, token, NEW_PIN, current_pin=PIN)

    assert _error(right)["code"] == "SESSION_REVOKED"
    assert _error(change)["code"] == "SESSION_REVOKED"
    assert (await _row(db, user.id)).pin_failed == 5
    assert await _pin_is(db, user.id, PIN)


async def test_the_lock_leaves_the_access_token_working_for_its_15_minutes(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """What the lock doesn't do (D-069, D-067), pinned so nobody mistakes it
    for protection: after five wrong PINs the sessions are revoked, refresh
    fails, and the access token still reads `/me` until it expires."""
    clock.freeze(START)
    token = await _sign_in(client, fake_providers, clock)
    user = await _account(db)
    await _with_pin(db, user)
    for _ in range(5):
        await _verify(client, token, WRONG)

    clock.advance(timedelta(minutes=14))
    still = await client.get("/v1/me", headers=_bearer(token))
    clock.advance(timedelta(minutes=1, seconds=1))
    expired = await client.get("/v1/me", headers=_bearer(token))

    assert still.status_code == 200
    assert _error(expired)["code"] == "TOKEN_EXPIRED"


async def test_a_fresh_sign_in_clears_the_count(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    token = await _sign_in(client, fake_providers, clock)
    user = await _account(db)
    await _with_pin(db, user)
    for _ in range(5):
        await _verify(client, token, WRONG)
    assert (await _row(db, user.id)).pin_failed == 5

    again = await _sign_in(client, fake_providers, clock)

    assert (await _row(db, user.id)).pin_failed == 0
    assert (await _verify(client, again, PIN)).status_code == 204


@pytest.mark.parametrize(
    "stored",
    [
        PasswordHasher.from_parameters(profiles.CHEAPEST).hash("x"),
        "not a hash at all",
        "$argon2id$v=19$m=19456,t=2,p=1$c2FsdHNhbHRzYWx0c2FsdA$" + "!" * 43,
    ],
    ids=["other parameters", "unreadable", "undecodable body"],
)
@pytest.mark.parametrize("failed", [0, 4])
async def test_a_hash_that_cant_be_checked_doesnt_count(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, stored: str, failed: int
) -> None:
    user, _ = await make_user()
    token = await _with_pin(db, user)
    user.pin_hash = stored
    user.pin_failed = failed
    await db.flush()

    response = await _verify(client, token, PIN)

    assert response.status_code == 401
    assert _error(response) == {
        "code": "PIN_INVALID",
        "message": "Your PIN can't be checked. Sign in again to set a new one.",
        "details": {"reset_required": True},
    }
    assert (await _row(db, user.id)).pin_failed == failed
    live = await db.scalar(
        text("select count(*) from users where id = :u"), {"u": user.id}
    )
    assert live == 1


async def test_a_try_given_back_after_the_count_was_cleared_stays_at_zero(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused hash gives its try back. If another request's right PIN
    cleared the count meanwhile, giving it back must leave 0, never -1: a
    count below zero would be a sixth guess."""
    user, _ = await make_user()
    user_id = user.id
    token = await _with_pin(db, user)

    async def cleared_meanwhile(pin: str, stored: str, settings: Any) -> PinCheck:
        async with db.begin():
            await db.execute(
                update(User).where(User.id == user_id).values(pin_failed=0)
            )
        return PinCheck.REFUSED

    monkeypatch.setattr(auth_service, "check_pin", cleared_meanwhile)
    response = await _verify(client, token, PIN)

    assert _error(response)["details"] == {"reset_required": True}
    assert (await _row(db, user_id)).pin_failed == 0


async def test_verifying_without_a_pin_is_not_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user()
    user_id = user.id

    response = await _verify(client, token, PIN)

    assert response.status_code == 422
    assert _error(response)["code"] == "NOT_ALLOWED"
    assert (await _row(db, user_id)).pin_failed == 0


@pytest.mark.parametrize("pin", ["12a4", "48290", 4829])
async def test_a_pin_that_isnt_four_digits_isnt_counted(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, pin: Any
) -> None:
    user, _ = await make_user()
    token = await _with_pin(db, user)

    response = await _verify(client, token, pin)

    assert response.status_code == 400
    assert (await _row(db, user.id)).pin_failed == 0


async def test_tries_made_at_once_are_each_counted_and_never_more_than_five(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eight wrong PINs at once, on eight connections: exactly five are ever
    checked, the fifth revokes, and the three past it are refused unchecked.
    Written for real, so it cleans up after itself."""
    phone = normalize_phone(f"+9198{uuid.uuid4().int % 10**8:08d}")
    async with (
        AsyncSession(test_engine, expire_on_commit=False) as setup,
        setup.begin(),
    ):
        account = await users_service.create_account(setup, phone, SETTINGS)
        account.user.pin_hash = await hash_pin(PIN, SETTINGS)
    user_id = account.user.id

    checked = 0
    real_check_pin = security.check_pin

    async def counting_check_pin(pin: str, stored: str, settings: Any) -> PinCheck:
        nonlocal checked
        checked += 1
        return await real_check_pin(pin, stored, settings)

    monkeypatch.setattr(auth_service, "check_pin", counting_check_pin)

    async def attempt() -> str:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            try:
                await auth_service.verify_pin(
                    session, SETTINGS, user_id=user_id, pin=WRONG
                )
            except AppError as error:
                return error.code
            return "verified"

    try:
        results = await asyncio.gather(*(attempt() for _ in range(8)))
        async with test_engine.connect() as conn:
            failed = await conn.scalar(
                text("select pin_failed from users where id = :u"), {"u": user_id}
            )
    finally:
        async with test_engine.begin() as conn:
            for table in ("notification_prefs", "wallets", "profiles"):
                await conn.execute(
                    text(f"delete from {table} where user_id = :u"), {"u": user_id}
                )
            await conn.execute(text("delete from users where id = :u"), {"u": user_id})

    assert checked == 5
    assert failed == 5
    assert sorted(results) == ["PIN_INVALID"] * 4 + ["SESSION_REVOKED"] * 4


# --- The limit -----------------------------------------------------------------------------


async def test_set_and_verify_share_ten_a_minute_per_user(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, clock: ModuleType
) -> None:
    clock.freeze(START)
    user, _ = await make_user()
    token = await _with_pin(db, user)
    other, _ = await make_user()
    other_token = await _with_pin(db, other)

    verified = [(await _verify(client, token, PIN)).status_code for _ in range(5)]
    set_tries = [(await _set(client, token, "1111")).status_code for _ in range(5)]
    eleventh = await _verify(client, token, PIN)
    someone_else = await _verify(client, other_token, PIN)
    skipped = await client.post("/v1/me/pin/skip", headers=_bearer(token))

    assert verified == [204] * 5 and set_tries == [400] * 5
    assert eleventh.status_code == 429
    assert _error(eleventh)["code"] == "RATE_LIMITED"
    assert someone_else.status_code == 204
    assert skipped.status_code == 200  # skipping hashes nothing; not the PIN's limit
    clock.advance(timedelta(seconds=61))
    assert (await _verify(client, token, PIN)).status_code == 204


# --- Skipping it ------------------------------------------------------------------------------


async def test_skipping_at_the_pin_step_moves_on_to_selfie_without_a_pin(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.PIN
    await db.flush()

    response = await client.post("/v1/me/pin/skip", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["onboarding_step"] == "selfie"
    assert response.json()["has_pin"] is False
    assert (await _row(db, user.id)).pin_hash is None


async def test_skipping_before_the_pin_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.INTERESTS
    await db.flush()

    response = await client.post("/v1/me/pin/skip", headers=_bearer(token))

    assert response.status_code == 403
    assert _error(response)["details"] == {"step": "interests"}


@pytest.mark.parametrize("step", [OnboardingStep.SELFIE, OnboardingStep.DONE])
async def test_skipping_after_the_pin_step_changes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token = await make_user(onboarded=step is OnboardingStep.DONE)
    user.onboarding_step = step
    await db.flush()

    response = await client.post("/v1/me/pin/skip", headers=_bearer(token))

    assert response.status_code == 200
    assert (await _row(db, user.id)).onboarding_step is step


# --- Rule 15 ---------------------------------------------------------------------------------


async def test_no_pin_hash_or_key_reaches_a_log_or_a_body(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    clock: ModuleType,
    captured_logs: CapturedLogs,
) -> None:
    clock.freeze(START)
    user, fresh = await make_user(onboarded=False)
    user.onboarding_step = OnboardingStep.PIN
    await db.flush()
    stale = _signed_in_at(user, START - timedelta(hours=1))
    responses = [
        await _set(client, fresh, "1212"),
        await _set(client, fresh, PIN),
        await _verify(client, stale, WRONG),
        await _set(client, stale, NEW_PIN, current_pin=WRONG),
        await _set(client, stale, NEW_PIN, current_pin=PIN),
        await _verify(client, stale, NEW_PIN),
    ]
    stored = (await _row(db, user.id)).pin_hash
    assert stored is not None
    user.pin_hash = PasswordHasher.from_parameters(profiles.CHEAPEST).hash("x")
    await db.flush()
    responses.append(await _verify(client, stale, NEW_PIN))

    assert [r.status_code for r in responses] == [400, 204, 401, 401, 204, 204, 401]
    seen = "\n".join([*(r.text for r in responses), captured_logs.text])
    # Request ids are random UUIDs, whose hex can hold four digits by chance.
    words = re.sub(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", "", seen)
    pins_typed = ["1212", PIN, WRONG, NEW_PIN]
    found = [p for p in pins_typed if re.search(rf"(?<![0-9]){p}(?![0-9])", words)]
    assert found == []
    secrets = [
        stored,
        stored.rsplit("$", 1)[-1],
        user.pin_hash,
        SETTINGS.CODE_PEPPER,
        security._code_key(SETTINGS, "pin").hex(),
    ]
    assert [s for s in secrets if s in seen] == []
    captured_logs.assert_listening()
