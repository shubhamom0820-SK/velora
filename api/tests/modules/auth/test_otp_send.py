"""`POST /v1/auth/otp/send` (T-3.2): Path B's codes, D-066's limits and cap,
D-064's local guard, and the same answer for every number."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core import ratelimit
from app.core.config import Settings
from app.core.db import get_session
from app.core.enums import BanKind
from app.core.providers import FakeProviders, Providers
from app.core.providers.sms import Msg91Sms, guard_real_sms
from app.core.security import E164, _code_key, decrypt_phone, hash_otp, hash_phone
from app.main import close_resources, create_app
from app.modules.auth import otp_store
from app.modules.auth.models import BannedIdentity
from tests.conftest import MakeUser, make_test_settings
from tests.infra import TEST_DATABASE_URL, session_for_the_app
from tests.keys import r2_settings, random_keys, sentry_settings, vapid_settings

pytestmark = pytest.mark.usefixtures("test_redis")

# Noon in IST: the daily cap's day is IST's.
START = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
PHONE = E164("+919812345678")
TYPED = "98123 45678"
SEND = "/v1/auth/otp/send"
SETTINGS = make_test_settings()


def _phone(i: int) -> str:
    """A different mobile number for each i: none of these ever gets an SMS."""
    return f"+9198765{i:05d}"


async def _send(client: AsyncClient, phone: str = TYPED, **headers: str) -> Response:
    return await client.post(SEND, json={"phone": phone}, headers=headers)


def _phone_hash(phone: str = PHONE) -> str:
    return hash_phone(E164(phone), SETTINGS)


def _assert_rate_limited(response: Response, retry_after_s: int) -> None:
    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "RATE_LIMITED",
            "message": "Too many tries. Wait a moment and try again.",
            "details": {"retry_after_s": retry_after_s},
        }
    }


@pytest.fixture
async def caddy_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """The app configured like the VMs: the client's IP comes from `Caddy-Client-IP`
    (D-056), so a test can be many clients."""
    app.state.settings = app.state.settings.model_copy(
        update={"CLIENT_IP_HEADER": "Caddy-Client-IP"}
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@asynccontextmanager
async def _client_for(
    settings: Settings, providers: Providers | None = None
) -> AsyncIterator[AsyncClient]:
    """A client for an app built from `settings`, sharing the test's `db`."""
    application = create_app(settings)
    application.dependency_overrides[get_session] = session_for_the_app
    if providers is not None:
        application.state.providers = providers
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        await close_resources(application)


async def _set_cap(db: AsyncSession, cap: int) -> None:
    await db.execute(
        text(
            "update app_config set value = to_jsonb(cast(:cap as int)) where key = :key"
        ),
        {"cap": cap, "key": "otp_sms_daily_cap"},
    )


# --- Sending ---------------------------------------------------------------------


async def test_a_six_digit_code_is_sent_and_stored_only_as_its_hash(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(START)

    response = await _send(client)

    assert response.status_code == 200
    assert response.json() == {"resend_after_s": 45}
    code = fake_providers.sms.last_code(PHONE)
    assert code is not None and re.fullmatch(r"[0-9]{6}", code)
    stored = await otp_store.read_code(test_redis, _phone_hash())
    assert stored == otp_store.StoredCode(
        code_hash=hash_otp(_phone_hash(), code, SETTINGS),
        attempts=0,
        expires_at_ms=int((START + timedelta(minutes=5)).timestamp() * 1000),
    )
    # Redis's own TTL only clears the key away; expiry is read from the clock.
    assert 0 < await test_redis.ttl(otp_store.code_key(_phone_hash())) <= 300


async def test_a_resend_replaces_the_code(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    await _send(client)
    clock.advance(timedelta(seconds=45))

    assert (await _send(client)).status_code == 200

    _first, second = (sent.code for sent in fake_providers.sms.sent)
    stored = await otp_store.read_code(test_redis, _phone_hash())
    assert stored is not None
    assert stored.code_hash == hash_otp(_phone_hash(), second, SETTINGS)
    assert len(fake_providers.sms.sent) == 2


async def test_the_body_must_carry_a_phone(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    for body in ({}, {"phone": "9" * 33}, {"phone": 9812345678}):
        response = await client.post(SEND, json=body)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    assert fake_providers.sms.sent == []


# --- D-070: numbers that can't receive an SMS ----------------------------------


@pytest.mark.parametrize(
    "cant_receive_sms",
    ["+91 22 2222 2222", "1800 123 4567", "140 123 4567"],
    ids=["landline", "toll-free", "140 series"],
)
async def test_a_number_that_cant_receive_an_sms_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    cant_receive_sms: str,
) -> None:
    response = await _send(client, cant_receive_sms)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Some of the information sent was not valid.",
            "details": {
                "fields": [{"field": "phone", "problem": "isn't a mobile number"}]
            },
        }
    }
    assert fake_providers.sms.sent == []


async def test_a_foreign_number_is_not_supported(
    db: AsyncSession, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    response = await _send(client, "+44 20 7946 0958")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PHONE_NOT_SUPPORTED"
    assert fake_providers.sms.sent == []


# --- D-066's limits ---------------------------------------------------------------


async def test_a_resend_within_45_seconds_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    assert (await _send(client)).status_code == 200

    clock.advance(timedelta(seconds=44))
    _assert_rate_limited(await _send(client), retry_after_s=1)
    clock.advance(timedelta(seconds=1))
    assert (await _send(client)).status_code == 200
    assert len(fake_providers.sms.sent) == 2


async def test_the_sixth_send_in_an_hour_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    for _ in range(5):
        assert (await _send(client)).status_code == 200
        clock.advance(timedelta(seconds=46))

    _assert_rate_limited(await _send(client), retry_after_s=3600 - 5 * 46)
    assert len(fake_providers.sms.sent) == 5

    # An hour after the first, it has left the window: one place opens.
    clock.advance(timedelta(seconds=3600 - 5 * 46))
    assert (await _send(client)).status_code == 200


async def test_the_eleventh_send_in_a_day_is_refused(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    for batch in range(2):
        for _ in range(5):
            assert (await _send(client)).status_code == 200
            clock.advance(timedelta(seconds=46))
        clock.advance(timedelta(hours=1))

    elapsed = 2 * (5 * 46 + 3600)
    _assert_rate_limited(await _send(client), retry_after_s=24 * 3600 - elapsed)
    assert len(fake_providers.sms.sent) == 10


async def test_the_21st_send_from_one_ip_in_an_hour_is_refused(
    db: AsyncSession,
    caddy_client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    ip = {"Caddy-Client-IP": "203.0.113.7"}
    for i in range(20):
        assert (await _send(caddy_client, _phone(i), **ip)).status_code == 200

    _assert_rate_limited(await _send(caddy_client, _phone(20), **ip), 3600)
    other = {"Caddy-Client-IP": "203.0.113.8"}
    assert (await _send(caddy_client, _phone(21), **other)).status_code == 200
    assert len(fake_providers.sms.sent) == 21


async def test_invalid_numbers_count_toward_the_ip_limit(
    db: AsyncSession, caddy_client: AsyncClient, clock: ModuleType
) -> None:
    clock.freeze(START)
    ip = {"Caddy-Client-IP": "203.0.113.7"}
    for _ in range(20):
        assert (await _send(caddy_client, "12345", **ip)).status_code == 400

    _assert_rate_limited(await _send(caddy_client, _phone(1), **ip), 3600)


async def test_the_101st_send_from_one_ipv6_48_in_an_hour_is_refused(
    db: AsyncSession,
    caddy_client: AsyncClient,
    fake_providers: FakeProviders,
    clock: ModuleType,
) -> None:
    """Each request from its own /64, so the per-IP limit never trips: only the
    /48's does. One cloud customer's /48 holds 65,536 /64s (D-066)."""
    clock.freeze(START)
    for i in range(100):
        ip = {"Caddy-Client-IP": f"2001:db8:abcd:{i:x}::1"}
        assert (await _send(caddy_client, _phone(i), **ip)).status_code == 200

    same_48 = {"Caddy-Client-IP": "2001:db8:abcd:ff00::1"}
    _assert_rate_limited(await _send(caddy_client, _phone(100), **same_48), 3600)
    other_48 = {"Caddy-Client-IP": "2001:db8:abce::1"}
    assert (await _send(caddy_client, _phone(101), **other_48)).status_code == 200
    assert len(fake_providers.sms.sent) == 101


async def _wrong_codes(redis: Redis, n: int, phone: str = PHONE) -> None:
    """What T-3.3's verify records for each wrong code (D-066)."""
    for _ in range(n):
        verdict = await ratelimit.hit(
            redis, "otp_wrong", _phone_hash(phone), limit=10, window_s=24 * 3600
        )
        assert verdict.allowed


async def test_a_number_at_ten_wrong_codes_in_24_hours_gets_no_more(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    await _wrong_codes(test_redis, 9)
    assert (await _send(client)).status_code == 200

    clock.advance(timedelta(hours=1))
    await _wrong_codes(test_redis, 1)
    _assert_rate_limited(await _send(client), retry_after_s=23 * 3600)
    assert len(fake_providers.sms.sent) == 1

    # The first nine leave the window 24 hours after they were made.
    clock.advance(timedelta(hours=23))
    assert (await _send(client)).status_code == 200


# --- The global daily cap (D-066) ---------------------------------------------------


async def test_past_the_daily_cap_no_code_is_sent(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    await _set_cap(db, 3)
    for i in range(3):
        assert (await _send(client, _phone(i))).status_code == 200

    response = await _send(client, _phone(3))

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "message": "We can't send sign-in codes right now. Try again later.",
        }
    }
    assert [sent.phone for sent in fake_providers.sms.sent] == [
        _phone(i) for i in range(3)
    ]
    assert await otp_store.read_code(test_redis, _phone_hash(_phone(3))) is None


async def test_the_cap_is_a_day_in_ist(
    db: AsyncSession, client: AsyncClient, clock: ModuleType
) -> None:
    clock.freeze(datetime(2026, 10, 3, 18, 29, tzinfo=UTC))  # 23:59 IST
    await _set_cap(db, 1)
    assert (await _send(client, _phone(0))).status_code == 200
    assert (await _send(client, _phone(1))).status_code == 503

    clock.advance(timedelta(minutes=1))  # 00:00 IST, 18:30 UTC
    assert (await _send(client, _phone(2))).status_code == 200


async def test_a_warning_is_logged_at_half_the_cap_once(
    db: AsyncSession, client: AsyncClient, clock: ModuleType
) -> None:
    clock.freeze(START)
    await _set_cap(db, 4)

    with capture_logs() as events:
        for i in range(4):
            assert (await _send(client, _phone(i))).status_code == 200

    warnings = [e for e in events if e["event"] == "otp_daily_cap_half_used"]
    assert warnings == [
        {
            "event": "otp_daily_cap_half_used",
            "log_level": "warning",
            "sent": 2,
            "cap": 4,
        }
    ]


# --- Banned and unknown numbers are answered as any other (D-066) ---------------


def _shape(response: Response) -> tuple[int, bytes, list[str]]:
    """Everything a client sees, but the request id, which differs anyway."""
    names = sorted(k for k in response.headers if k.lower() != "x-request-id")
    return response.status_code, response.content, names


async def test_a_banned_number_is_answered_as_any_other_and_sent_nothing(
    db: AsyncSession,
    client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    banned = _phone(1)
    db.add(
        BannedIdentity(
            kind=BanKind.PHONE_HASH, value=_phone_hash(banned), reason="underage"
        )
    )
    await db.flush()

    to_banned = await _send(client, banned)
    to_anyone = await _send(client, _phone(2))

    assert _shape(to_banned) == _shape(to_anyone)
    assert [sent.phone for sent in fake_providers.sms.sent] == [_phone(2)]
    # A code is stored, never sent, so a guess at verify is answered alike.
    assert await otp_store.read_code(test_redis, _phone_hash(banned)) is not None
    # And it counts against the same limits.
    _assert_rate_limited(await _send(client, banned), retry_after_s=45)


async def test_a_known_and_an_unknown_number_are_answered_alike(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    fake_providers: FakeProviders,
) -> None:
    user, _ = await make_user()
    assert user.phone_enc is not None
    known_phone = decrypt_phone(user.phone_enc, SETTINGS)
    known = await _send(client, known_phone)
    unknown = await _send(client, _phone(3))

    assert _shape(known) == _shape(unknown)
    assert len(fake_providers.sms.sent) == 2


# --- Served only for msg91 and fake (D-066) --------------------------------------

_DEPLOYED: dict[str, Any] = {
    "DATABASE_URL": TEST_DATABASE_URL,
    "REDIS_URL": "rediss://default:x@redis.example:6379/0",
    "CLIENT_IP_HEADER": "Caddy-Client-IP",
    # Path A names its project (D-085).
    "FIREBASE_PROJECT_ID": "velora-test",
    "SMS_PROVIDER": "msg91",
    "PAYMENTS_PROVIDER": "razorpay",
    "MODERATION_PROVIDER": "sightengine",
    "FACEMATCH_PROVIDER": "sface",
    "STORAGE_PROVIDER": "s3",
    **r2_settings(),
    "PUSH_PROVIDER": "webpush",
    **vapid_settings(),
    **sentry_settings(),
    **random_keys(),
}


def _assert_not_found(response: Response) -> None:
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not found."}}


@pytest.mark.parametrize("env", ["staging", "production"])
async def test_staging_and_production_on_firebase_serve_no_path_b(env: str) -> None:
    settings = Settings(
        _env_file=None, ENV=env, AUTH_PHONE_PROVIDER="firebase", **_DEPLOYED
    )

    async with _client_for(settings) as client:
        _assert_not_found(await _send(client))


async def test_locally_on_firebase_there_is_no_path_b(db: AsyncSession) -> None:
    settings = make_test_settings().model_copy(
        update={"AUTH_PHONE_PROVIDER": "firebase"}
    )

    async with _client_for(settings) as client:
        _assert_not_found(await _send(client))


async def test_a_provider_named_later_serves_no_path_b() -> None:
    """The routes name the providers they serve (rule 16). One nobody has named
    yet gets nothing, where a blacklist (`!= "firebase"`) would serve it."""
    settings = make_test_settings().model_copy(update={"AUTH_PHONE_PROVIDER": "otp-co"})

    async with _client_for(settings) as client:
        _assert_not_found(await _send(client))


async def test_msg91_serves_path_b(db: AsyncSession) -> None:
    """Served, so the request reaches D-064's guard rather than a 404."""
    settings = make_test_settings().model_copy(
        update={"AUTH_PHONE_PROVIDER": "msg91", "SMS_PROVIDER": "msg91"}
    )

    async with _client_for(settings) as client:
        response = await _send(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


# --- D-064's local guard, end to end -----------------------------------------------


class RecordingSms:
    """Stands in for a real provider and records what reaches it: Msg91Sms has
    no HTTP client to watch until P-46."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent.append((phone, code))


SEEDED = "+919000000101"  # a profile's number in seed/data.py, maybe someone's


async def test_locally_a_seeded_number_never_reaches_a_real_provider(
    db: AsyncSession, test_redis: Redis, clock: ModuleType
) -> None:
    clock.freeze(START)
    settings = make_test_settings().model_copy(
        update={"SMS_PROVIDER": "msg91", "SMS_LOCAL_ALLOWED_TO": (PHONE,)}
    )
    real = RecordingSms()
    providers = FakeProviders().as_providers()
    providers = Providers(
        sms=guard_real_sms(real, settings),
        payments=providers.payments,
        moderation=providers.moderation,
        facematch=providers.facematch,
        push=providers.push,
        storage=providers.storage,
        firebase_keys=providers.firebase_keys,
    )

    async with _client_for(settings, providers) as client:
        seeded = await _send(client, SEEDED)
        listed = await _send(client, TYPED)

    assert seeded.status_code == 503
    assert seeded.json() == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "message": "Locally, a real SMS provider texts only the numbers in "
            "SMS_LOCAL_ALLOWED_TO (D-064).",
        }
    }
    assert await otp_store.read_code(test_redis, _phone_hash(SEEDED)) is None
    assert listed.status_code == 200
    assert [phone for phone, _ in real.sent] == [PHONE]


async def test_locally_the_real_msg91_is_wrapped_too(db: AsyncSession) -> None:
    """Not a stand-in: the app's own providers, as build_providers makes them."""
    settings = make_test_settings().model_copy(update={"SMS_PROVIDER": "msg91"})

    async with _client_for(settings) as client:
        response = await _send(client, SEEDED)

    assert response.status_code == 503
    assert "SMS_LOCAL_ALLOWED_TO" in response.json()["error"]["message"]


async def test_msg91_raises_so_a_send_fails_loudly_and_keeps_no_code(
    db: AsyncSession, test_redis: Redis
) -> None:
    """Until P-46 a listed number reaches Msg91Sms, which raises: the person is
    told it failed, never "code sent", and no code is left to guess at."""
    settings = make_test_settings().model_copy(
        update={"SMS_PROVIDER": "msg91", "SMS_LOCAL_ALLOWED_TO": (PHONE,)}
    )

    async with _client_for(settings) as client:
        response = await _send(client)

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL", "message": "Something went wrong on our end."}
    }
    assert await otp_store.read_code(test_redis, _phone_hash()) is None


async def test_msg91_itself_raises() -> None:
    with pytest.raises(NotImplementedError, match="P-46"):
        await Msg91Sms().send_otp(PHONE, "482193")


# --- Rule 15: nothing secret in any response or log ---------------------------------


def _formats(phone: str) -> list[str]:
    national = phone.removeprefix("+91")
    return [
        phone,
        phone.removeprefix("+"),
        national,
        f"{national[:5]} {national[5:]}",
        f"{national[:5]}-{national[5:]}",
    ]


async def test_no_number_code_hash_or_key_reaches_a_response_or_log(
    db: AsyncSession,
    caddy_client: AsyncClient,
    fake_providers: FakeProviders,
    test_redis: Redis,
    clock: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clock.freeze(START)
    banned = _phone(1)
    db.add(BannedIdentity(kind=BanKind.PHONE_HASH, value=_phone_hash(banned)))
    # The banned number counts against the cap like any other (D-066), so the
    # warning comes at its send: 2 of 4.
    await _set_cap(db, 4)
    ip = {"Caddy-Client-IP": "203.0.113.7"}

    with capture_logs() as events:
        responses = [
            await _send(caddy_client, TYPED, **ip),  # sent
            await _send(caddy_client, TYPED, **ip),  # too soon
            await _send(caddy_client, banned, **ip),  # banned
            await _send(caddy_client, _phone(2), **ip),  # sent
            await _send(caddy_client, _phone(3), **ip),  # sent: 4 of 4
            await _send(caddy_client, _phone(4), **ip),  # past the cap
            await _send(caddy_client, "+91 22 2222 2222", **ip),  # a landline
        ]

    assert [r.status_code for r in responses] == [200, 429, 200, 200, 200, 503, 400]
    assert any(e["event"] == "otp_daily_cap_half_used" for e in events)
    out, err = capsys.readouterr()
    seen = "\n".join(
        [
            *(r.text for r in responses),
            *(json.dumps(dict(r.headers)) for r in responses),
            *(json.dumps(e, default=str) for e in events),
            out,
            err,
        ]
    )

    phones = [PHONE, banned, _phone(2), _phone(3), _phone(4), "+912222222222"]
    secrets: list[str] = [f for phone in phones for f in _formats(phone)]
    for phone in phones[:5]:
        phone_hash = _phone_hash(phone)
        secrets += [phone_hash, phone_hash.upper()]
    for sent in fake_providers.sms.sent:
        secrets += [sent.code, hash_otp(_phone_hash(sent.phone), sent.code, SETTINGS)]
    for name in ("CODE_PEPPER", "PHONE_PEPPER", "JWT_SECRET"):
        secrets.append(getattr(SETTINGS, name))
    secrets += [*SETTINGS.PHONE_ENC_KEY, _code_key(SETTINGS, "otp").hex()]

    assert len(fake_providers.sms.sent) == 3
    assert [s for s in secrets if s in seen] == []
