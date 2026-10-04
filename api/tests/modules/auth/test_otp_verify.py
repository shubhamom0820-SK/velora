"""`POST /v1/auth/otp/verify` (T-3.3): the code's 5 tries and 5 minutes, the
number's 10 wrong codes a day (D-066), find-or-create in one transaction, who
may sign in (D-067), the session and its two cookies (D-054, D-055, D-067), and
`auth_time` (D-071)."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core import ratelimit
from app.core.config import Settings
from app.core.db import get_session
from app.core.enums import BanKind, OnboardingStep, Role, UserStatus
from app.core.providers import FakeProviders
from app.core.security import (
    E164,
    _code_key,
    decode_access_token,
    hash_otp,
    hash_phone,
    hash_token,
)
from app.main import close_resources, create_app
from app.modules.auth import otp_store, service
from app.modules.auth.models import BannedIdentity, Session
from app.modules.notifications.models import NotificationPrefs
from app.modules.profiles.models import Profile
from app.modules.users import repository as users_repository
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.wallet.models import Wallet
from tests.conftest import MakeUser, make_test_settings
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL, session_for_the_app
from tests.keys import r2_settings, random_keys

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
PHONE = E164("+919812345678")
TYPED = "98123 45678"
VERIFY = "/v1/auth/otp/verify"
SETTINGS = make_test_settings()
THIRTY_DAYS = 30 * 24 * 60 * 60


def _phone_hash(phone: str = PHONE) -> str:
    return hash_phone(E164(phone), SETTINGS)


async def _send(client: AsyncClient, phone: str = TYPED) -> Response:
    response = await client.post("/v1/auth/otp/send", json={"phone": phone})
    assert response.status_code == 200
    return response


async def _verify(client: AsyncClient, otp: str, phone: str = TYPED) -> Response:
    return await client.post(VERIFY, json={"phone": phone, "otp": otp})


async def _code_for(
    client: AsyncClient, fake_providers: FakeProviders, phone: str = TYPED
) -> str:
    await _send(client, phone)
    sent = fake_providers.sms.sent[-1]
    return sent.code


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _count(db: AsyncSession, model: type[Any]) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def _accounts(db: AsyncSession, phone: str = PHONE) -> int:
    """Accounts on this number: never every user in the table, since other
    tests in the run commit users of their own (06-TESTING)."""
    return int(
        await db.scalar(
            select(func.count()).where(User.phone_hash == _phone_hash(phone))
        )
        or 0
    )


# --- The right code signs in, creating the account the first time ---------------


async def test_a_new_number_gets_an_account_of_four_rows_and_a_session(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    code = await _code_for(client, fake_providers)

    response = await _verify(client, code)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "user"}
    user = await db.scalar(select(User).where(User.phone_hash == _phone_hash()))
    assert user is not None
    assert (user.status, user.role, user.onboarding_step) == (
        UserStatus.ACTIVE,
        Role.USER,
        OnboardingStep.DOB,
    )
    assert await db.get(Profile, user.id) is not None
    wallet = await db.get(Wallet, user.id)
    assert wallet is not None and wallet.balance == 0
    assert await db.get(NotificationPrefs, user.id) is not None
    sessions = (await db.scalars(select(Session))).all()
    assert len(sessions) == 1
    assert sessions[0].user_id == user.id
    assert sessions[0].expires_at == START + timedelta(days=30)
    assert sessions[0].auth_time == START


async def test_me_comes_back_with_exactly_its_fields(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    code = await _code_for(client, fake_providers)

    me = (await _verify(client, code)).json()["user"]

    user = await db.scalar(select(User).where(User.phone_hash == _phone_hash()))
    assert user is not None
    assert me == {
        "id": str(user.id),
        "role": "user",
        "status": "active",
        "onboarding_step": "dob",
        "gender": None,
        "age": None,
        "is_verified": False,
        "has_pin": False,
        "referral_code": user.referral_code,
        "balance": 0,
        "profile": {
            "first_name": None,
            "username": None,
            "about": None,
            "hometown": None,
            "city": None,
            "seeking": None,
            "intent_ids": [],
            "interest_ids": [],
            "is_hidden": False,
            "hide_age": False,
            "hide_distance": False,
            "show_kudos": True,
            "show_gifts": True,
        },
    }


async def test_an_existing_number_signs_in_without_a_second_account(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    user, _ = await make_user(gender="female")
    phone = await _phone_of(db, user)
    users_before = await _count(db, User)
    code = await _code_for(client, fake_providers, phone)

    response = await _verify(client, code, phone)

    assert response.status_code == 200
    me = response.json()["user"]
    assert me["id"] == str(user.id)
    assert (me["gender"], me["age"], me["onboarding_step"]) == ("female", 25, "done")
    assert me["profile"]["first_name"] == "Test"
    assert await _count(db, User) == users_before
    assert await _count(db, Profile) == users_before


async def _phone_of(db: AsyncSession, user: User) -> str:
    from app.core.security import decrypt_phone

    return decrypt_phone(user.phone_enc, SETTINGS)


async def test_me_counts_age_in_ist(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """Midnight IST on someone's birthday is still the day before in UTC: the
    age is India's (D-029)."""
    user, _ = await make_user()  # born 1 January, 25 years before this year
    phone = await _phone_of(db, user)
    born = user.dob
    assert born is not None
    clock.freeze(
        datetime(born.year + 26, 1, 1, 0, 0, tzinfo=UTC)
        - timedelta(hours=5, minutes=30)
    )
    code = await _code_for(client, fake_providers, phone)

    me = (await _verify(client, code, phone)).json()["user"]

    assert me["age"] == 26


async def test_the_access_token_carries_auth_time_the_sign_in(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    code = await _code_for(client, fake_providers)
    clock.advance(timedelta(seconds=30))

    token = (await _verify(client, code)).json()["access_token"]

    claims = jwt.decode(token, options={"verify_signature": False})
    assert set(claims) == {"sub", "role", "aud", "iat", "exp", "auth_time"}
    assert claims["auth_time"] == int((START + timedelta(seconds=30)).timestamp())
    assert decode_access_token(token, SETTINGS).auth_time == START + timedelta(
        seconds=30
    )


async def test_sessions_keep_no_ip_address_or_user_agent(
    db: AsyncSession,
    fake_providers: FakeProviders,
    app: FastAPI,
) -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"User-Agent": "Mozilla/5.0 (test)", "X-Forwarded-For": "1.2.3.4"},
    ) as client:
        code = await _code_for(client, fake_providers)
        assert (await _verify(client, code)).status_code == 200

    rows = (await db.execute(text("select ip, user_agent from sessions"))).all()
    assert [tuple(row) for row in rows] == [(None, None)]


async def test_the_refresh_token_is_stored_only_as_its_hash(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    code = await _code_for(client, fake_providers)

    response = await _verify(client, code)

    refresh = _cookies(response)["refresh_local"].value
    stored = (await db.scalars(select(Session.token_hash))).all()
    assert stored == [hash_token(refresh)]
    assert refresh not in response.text


async def test_each_sign_in_starts_its_own_session_family(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    for _ in range(2):
        code = await _code_for(client, fake_providers)
        assert (await _verify(client, code)).status_code == 200
        clock.advance(timedelta(minutes=1))

    families = (await db.scalars(select(Session.family_id))).all()
    assert len(set(families)) == 2


# --- Wrong, old and missing codes (D-066) -------------------------------------------


async def test_a_wrong_code_says_how_many_tries_are_left(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
) -> None:
    code = await _code_for(client, fake_providers)

    for left in (4, 3, 2, 1):
        response = await _verify(client, _wrong(code))
        assert response.status_code == 400
        assert _error(response) == {
            "code": "OTP_INVALID",
            "message": "That code isn't right.",
            "details": {"attempts_left": left},
        }

    stored = await otp_store.read_code(test_redis, _phone_hash())
    assert stored is not None and stored.attempts == 4
    assert (await _verify(client, code)).status_code == 200


async def test_the_fifth_wrong_code_uses_the_code_up(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
) -> None:
    code = await _code_for(client, fake_providers)
    for _ in range(4):
        await _verify(client, _wrong(code))

    fifth = await _verify(client, _wrong(code))

    assert fifth.status_code == 429
    assert _error(fifth) == {
        "code": "OTP_TOO_MANY",
        "message": "Too many wrong codes. Try again later.",
    }
    assert await otp_store.read_code(test_redis, _phone_hash()) is None
    # The right code is no use now either.
    assert _error(await _verify(client, code))["code"] == "OTP_EXPIRED"
    assert await _accounts(db) == 0


async def test_a_code_past_five_minutes_has_expired(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    code = await _code_for(client, fake_providers)

    clock.advance(timedelta(minutes=4, seconds=59))
    assert await otp_store.read_code(test_redis, _phone_hash()) is not None
    clock.advance(timedelta(seconds=1))
    response = await _verify(client, code)

    assert response.status_code == 400
    assert _error(response) == {
        "code": "OTP_EXPIRED",
        "message": "That code has expired. Ask for a new one.",
    }
    assert await otp_store.read_code(test_redis, _phone_hash()) is None


async def test_a_code_signs_in_once(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    code = await _code_for(client, fake_providers)
    assert (await _verify(client, code)).status_code == 200

    again = await _verify(client, code)

    assert _error(again)["code"] == "OTP_EXPIRED"
    assert await _count(db, Session) == 1


async def test_a_number_never_sent_a_code_gets_expired_and_no_count(
    db: AsyncSession, client: AsyncClient, test_redis: Redis
) -> None:
    response = await _verify(client, "123456")

    assert _error(response)["code"] == "OTP_EXPIRED"
    assert (
        await ratelimit.used(test_redis, "otp_wrong", _phone_hash(), window_s=24 * 3600)
        == 0
    )


async def test_a_resend_replaces_the_code_and_its_tries(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    old = await _code_for(client, fake_providers)
    await _verify(client, _wrong(old))
    clock.advance(timedelta(seconds=45))
    new = await _code_for(client, fake_providers)

    if old != new:
        assert _error(await _verify(client, old))["code"] == "OTP_INVALID"
    response = await _verify(client, _wrong(new))
    # One wrong try on each code, two in the number's day: four left on this one.
    assert _error(response)["details"] == {"attempts_left": 4 if old == new else 3}
    assert (await _verify(client, new)).status_code == 200


async def test_ten_wrong_codes_in_a_day_lock_the_number(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """Across codes: four wrong on one, four on the next, then the tries left
    are the number's, not the code's, and the tenth locks it for 24 hours."""
    clock.freeze(START)
    for _ in range(2):
        code = await _code_for(client, fake_providers)
        lefts = [
            _error(await _verify(client, _wrong(code)))["details"]["attempts_left"]
            for _ in range(4)
        ]
        assert lefts == [4, 3, 2, 1]
        clock.advance(timedelta(minutes=1))

    third = await _code_for(client, fake_providers)
    ninth = await _verify(client, _wrong(third))
    assert _error(ninth) == {
        "code": "OTP_INVALID",
        "message": "That code isn't right.",
        "details": {"attempts_left": 1},
    }
    tenth = await _verify(client, _wrong(third))
    assert tenth.status_code == 429
    assert _error(tenth)["code"] == "OTP_TOO_MANY"

    # Locked: verify refuses before reading, and send refuses too (T-3.2).
    assert _error(await _verify(client, third))["code"] == "OTP_TOO_MANY"
    send = await client.post("/v1/auth/otp/send", json={"phone": TYPED})
    assert send.status_code == 429
    assert await _accounts(db) == 0

    clock.advance(timedelta(hours=24))
    fourth = await _code_for(client, fake_providers)
    assert (await _verify(client, fourth)).status_code == 200


async def test_a_number_already_at_ten_wrong_codes_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    """Set directly, as T-3.2's send test does: verify refuses before reading."""
    clock.freeze(START)
    code = await _code_for(client, fake_providers)
    for _ in range(10):
        await ratelimit.hit(
            test_redis, "otp_wrong", _phone_hash(), limit=10, window_s=24 * 3600
        )

    response = await _verify(client, code)

    assert response.status_code == 429
    assert _error(response)["code"] == "OTP_TOO_MANY"
    assert await _accounts(db) == 0


@pytest.mark.parametrize("otp", ["12345", "1234567", "12345a", "", "١٢٣٤٥٦"])
async def test_a_code_that_isnt_six_digits_is_refused_and_not_counted(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    otp: str,
) -> None:
    await _code_for(client, fake_providers)

    response = await _verify(client, otp)

    assert response.status_code == 400
    assert _error(response)["code"] == "VALIDATION_ERROR"
    stored = await otp_store.read_code(test_redis, _phone_hash())
    assert stored is not None and stored.attempts == 0


async def test_only_one_of_two_requests_with_the_right_code_consumes_it(
    test_redis: Redis,
) -> None:
    """The code is used up atomically: of two at once, one wins."""
    code_hash = hash_otp(_phone_hash(), "482193", SETTINGS)
    await otp_store.save_code(
        test_redis,
        _phone_hash(),
        code_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),  # noqa: TID251
        ttl_s=300,
    )

    results = await asyncio.gather(
        *(
            otp_store.consume_code(test_redis, _phone_hash(), code_hash)
            for _ in range(20)
        )
    )

    assert sorted(results) == [False] * 19 + [True]


async def test_a_code_replaced_meanwhile_is_not_consumed_by_the_old_one(
    test_redis: Redis,
) -> None:
    old = hash_otp(_phone_hash(), "111111", SETTINGS)
    new = hash_otp(_phone_hash(), "222222", SETTINGS)
    expires = datetime.now(UTC) + timedelta(minutes=5)  # noqa: TID251
    await otp_store.save_code(
        test_redis, _phone_hash(), new, expires_at=expires, ttl_s=300
    )

    assert await otp_store.consume_code(test_redis, _phone_hash(), old) is False
    assert await otp_store.read_code(test_redis, _phone_hash()) is not None


# --- Who may sign in (D-067) ----------------------------------------------------------


async def _with_status(
    make_user: MakeUser, db: AsyncSession, status: UserStatus
) -> str:
    user, _ = await make_user()
    user.status = status
    await db.flush()
    return await _phone_of(db, user)


@pytest.mark.parametrize(
    ("status", "code", "message"),
    [
        (UserStatus.BANNED, "ACCOUNT_BANNED", "This account has been banned."),
        (
            UserStatus.FROZEN,
            "ACCOUNT_FROZEN",
            "This account is frozen while we look into it.",
        ),
        (UserStatus.DELETED, "FORBIDDEN", "This account can't sign in."),
    ],
)
async def test_banned_frozen_and_deleted_accounts_cant_sign_in(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    test_redis: Redis,
    status: UserStatus,
    code: str,
    message: str,
) -> None:
    phone = await _with_status(make_user, db, status)
    otp = await _code_for(client, fake_providers, phone)

    response = await _verify(client, otp, phone)

    assert response.status_code == 403
    assert _error(response) == {"code": code, "message": message}
    assert "set-cookie" not in response.headers
    assert await _count(db, Session) == 0
    # The code is spent: proving the number doesn't open a second try.
    assert await otp_store.read_code(test_redis, _phone_hash(phone)) is None


async def test_a_paused_account_signs_in(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    phone = await _with_status(make_user, db, UserStatus.PAUSED)
    otp = await _code_for(client, fake_providers, phone)

    response = await _verify(client, otp, phone)

    assert response.status_code == 200
    assert response.json()["user"]["status"] == "paused"


async def test_a_status_added_later_cant_sign_in(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Who may sign in is a list of who may (D-067). Taking paused off it, as
    if it were a status nobody had listed yet, refuses it: a list of who may
    not would let it through."""
    monkeypatch.setattr(users_service, "MAY_SIGN_IN", frozenset({UserStatus.ACTIVE}))
    phone = await _with_status(make_user, db, UserStatus.PAUSED)
    otp = await _code_for(client, fake_providers, phone)

    response = await _verify(client, otp, phone)

    assert response.status_code == 403
    assert _error(response)["code"] == "FORBIDDEN"


async def test_a_banned_number_with_the_right_code_gets_no_account(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its code was stored, never sent (T-3.2). Someone who guessed it still
    gets no account: the ban shows here, and nothing is written."""
    db.add(
        BannedIdentity(kind=BanKind.PHONE_HASH, value=_phone_hash(), reason="underage")
    )
    await db.flush()
    monkeypatch.setattr(service, "new_otp_code", lambda: "482193")
    await _send(client)
    assert fake_providers.sms.sent == []

    response = await _verify(client, "482193")

    assert response.status_code == 403
    assert _error(response) == {
        "code": "ACCOUNT_BANNED",
        "message": "This account has been banned.",
    }
    assert "set-cookie" not in response.headers
    assert await _accounts(db) == 0
    assert await _count(db, Session) == 0


# --- The cookies (D-054, D-055, D-067) ---------------------------------------------


class _Cookie:
    def __init__(self, value: str, attributes: dict[str, str | bool]) -> None:
        self.value = value
        self.attributes = attributes


def _cookies(response: Response) -> dict[str, _Cookie]:
    """Each Set-Cookie header, parsed by hand: name, value, and every attribute
    exactly as sent, so a test can say "these and nothing else"."""
    cookies: dict[str, _Cookie] = {}
    for header in response.headers.get_list("set-cookie"):
        first, *rest = [part.strip() for part in header.split(";")]
        name, _, value = first.partition("=")
        attributes: dict[str, str | bool] = {}
        for part in rest:
            key, sep, val = part.partition("=")
            attributes[key.lower()] = val if sep else True
        cookies[name] = _Cookie(value, attributes)
    return cookies


async def _signed_in(client: AsyncClient, fake_providers: FakeProviders) -> Response:
    code = await _code_for(client, fake_providers)
    response = await _verify(client, code)
    assert response.status_code == 200
    return response


async def test_the_refresh_cookie_is_httponly_secure_lax_on_v1_auth_and_host_only(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    refresh = _cookies(await _signed_in(client, fake_providers))["refresh_local"]

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", refresh.value)
    assert refresh.attributes == {
        "httponly": True,
        "max-age": str(THIRTY_DAYS),
        "path": "/v1/auth",
        "samesite": "lax",
        "secure": True,
    }


async def test_the_csrf_cookie_is_readable_secure_lax_site_wide(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    """Locally COOKIE_DOMAIN is empty, so it's host-only too."""
    csrf = _cookies(await _signed_in(client, fake_providers))["csrf_local"]

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", csrf.value)
    assert csrf.attributes == {
        "max-age": str(THIRTY_DAYS),
        "path": "/",
        "samesite": "lax",
        "secure": True,
    }


async def test_exactly_two_cookies_are_set(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    assert set(_cookies(await _signed_in(client, fake_providers))) == {
        "refresh_local",
        "csrf_local",
    }


@asynccontextmanager
async def _client_for(
    settings: Settings, fakes: FakeProviders | None = None
) -> AsyncIterator[AsyncClient]:
    application = create_app(settings)
    application.dependency_overrides[get_session] = session_for_the_app
    application.state.providers = (fakes or FakeProviders()).as_providers()
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        await close_resources(application)


_DEPLOYED: dict[str, Any] = {
    "DATABASE_URL": TEST_DATABASE_URL,
    "REDIS_URL": TEST_REDIS_URL,
    "CLIENT_IP_HEADER": "Fly-Client-IP",
    **random_keys(),
}


@pytest.mark.parametrize(
    ("env", "suffix", "domain"),
    [
        ("staging", "staging", "staging.veloraapp.co.in"),
        ("production", "prod", "veloraapp.co.in"),
    ],
)
async def test_each_environment_names_its_cookies_and_scopes_csrf_to_its_domain(
    db: AsyncSession, env: str, suffix: str, domain: str
) -> None:
    """Both names come from ENV (D-055), and the CSRF cookie's Domain from
    COOKIE_DOMAIN; the refresh cookie has none anywhere (D-054). Path B never
    runs there, so the app is built here with fakes, its settings swapped
    after validation, to read the cookies a sign-in would set."""
    settings = make_test_settings().model_copy(
        update={"ENV": env, "COOKIE_DOMAIN": domain}
    )

    fakes = FakeProviders()

    async with _client_for(settings, fakes) as client:
        await client.post("/v1/auth/otp/send", json={"phone": TYPED})
        response = await _verify(client, fakes.sms.sent[-1].code)

    cookies = _cookies(response)
    assert set(cookies) == {f"refresh_{suffix}", f"csrf_{suffix}"}
    assert "domain" not in cookies[f"refresh_{suffix}"].attributes
    assert cookies[f"csrf_{suffix}"].attributes["domain"] == domain
    claims = jwt.decode(
        response.json()["access_token"], options={"verify_signature": False}
    )
    assert claims["aud"] == env


def test_an_environment_without_a_suffix_has_no_cookie_name() -> None:
    """No fallback (D-055): a bare `refresh` would be the name every
    environment named later collides with."""
    from app.modules.auth.cookies import csrf_cookie_name, refresh_cookie_name

    settings = make_test_settings().model_copy(update={"ENV": "preview"})

    with pytest.raises(KeyError):
        refresh_cookie_name(settings)
    with pytest.raises(KeyError):
        csrf_cookie_name(settings)


# --- Served only for msg91 and fake (D-066) ------------------------------------------


@pytest.mark.parametrize("env", ["staging", "production"])
async def test_staging_and_production_on_firebase_serve_no_verify(env: str) -> None:
    settings = Settings(
        _env_file=None,
        ENV=env,
        AUTH_PHONE_PROVIDER="firebase",
        FIREBASE_PROJECT_ID="velora-test",
        SMS_PROVIDER="msg91",
        PAYMENTS_PROVIDER="razorpay",
        MODERATION_PROVIDER="sightengine",
        FACEMATCH_PROVIDER="rekognition",
        STORAGE_PROVIDER="s3",
        PUSH_PROVIDER="webpush",
        **{
            **_DEPLOYED,
            **r2_settings(),
            "REDIS_URL": "rediss://default:x@redis.example:6379/0",
        },
    )

    async with _client_for(settings) as client:
        response = await _verify(client, "123456")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not found."}}


# --- Referral codes (T-3.3) --------------------------------------------------------------


async def test_a_new_account_gets_an_eight_character_referral_code(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    me = (await _signed_in(client, fake_providers)).json()["user"]

    assert re.fullmatch(r"[23456789ABCDEFGHJKMNPQRSTVWXYZ]{8}", me["referral_code"])


def test_referral_codes_never_hold_a_character_read_aloud_two_ways() -> None:
    codes = "".join(users_service.new_referral_code() for _ in range(2000))

    assert set(codes) == set("23456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert not set(codes) & set("01OILU")


async def test_a_referral_code_already_taken_is_drawn_again(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    taken, _ = await make_user()
    draws = iter([taken.referral_code.lower(), "ZZZZ2222"])
    monkeypatch.setattr(users_service, "new_referral_code", lambda: next(draws))

    account = await users_service.create_account(db, PHONE, SETTINGS)

    assert account.user.referral_code == "ZZZZ2222"


async def test_find_or_create_finds_an_account_created_meanwhile(
    db: AsyncSession, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two sign-ins for one new number at once: the second's insert hits the
    unique phone hash, and it finds the account instead of failing."""
    user, _ = await make_user()
    phone = E164(await _phone_of(db, user))
    real = users_repository.user_by_phone_hash
    calls = 0

    async def first_look_misses(session: AsyncSession, phone_hash: str) -> User | None:
        nonlocal calls
        calls += 1
        return None if calls == 1 else await real(session, phone_hash)

    monkeypatch.setattr(users_repository, "user_by_phone_hash", first_look_misses)

    found, created = await users_service.find_or_create_account(db, phone, SETTINGS)

    assert (found.id, created) == (user.id, False)
    assert await _accounts(db, phone) == 1


# --- Rule 15 -----------------------------------------------------------------------------------


async def test_no_number_code_token_or_key_reaches_a_log_or_the_body(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with capture_logs() as events:
        code = await _code_for(client, fake_providers)
        wrong = await _verify(client, _wrong(code))
        right = await _verify(client, code)
        service.log.info("probe")  # proves the capture is listening

    assert [e["event"] for e in events] == ["probe"]
    cookies = _cookies(right)
    refresh = cookies["refresh_local"].value
    out, err = capsys.readouterr()
    body_and_logs = "\n".join(
        [
            wrong.text,
            right.text,
            *(json.dumps(e, default=str) for e in events),
            out,
            err,
        ]
    )
    national = PHONE.removeprefix("+91")
    secrets = [
        PHONE,
        national,
        f"{national[:5]} {national[5:]}",
        _phone_hash(),
        code,
        _wrong(code),
        hash_otp(_phone_hash(), code, SETTINGS),
        refresh,
        hash_token(refresh),
        SETTINGS.CODE_PEPPER,
        SETTINGS.PHONE_PEPPER,
        SETTINGS.JWT_SECRET,
        *SETTINGS.PHONE_ENC_KEY,
        _code_key(SETTINGS, "otp").hex(),
    ]
    assert [s for s in secrets if s in body_and_logs] == []
    # The CSRF value is in its cookie and nowhere in the body.
    assert cookies["csrf_local"].value not in right.text
