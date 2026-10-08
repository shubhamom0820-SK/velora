"""`POST /v1/auth/firebase` (T-3.14, D-085): Path A's token exchange.

A Firebase ID token is checked as Google documents (signature, `aud`, `iss`,
times), must be a phone sign-in no older than 5 minutes, signs in once, and
then ends in T-3.3's `sign_in()`: India only, banned numbers refused, the
account found or created, the session and both cookies. 10 an IP and 5 a phone
an hour. Served only where `AUTH_PHONE_PROVIDER` is `firebase`.

Tokens are minted by `FakeFirebaseKeys`, which plays Google's part with a key
of its own; the checks they meet are the real ones.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core.config import PUBLIC_TEST_KEYS, Settings
from app.core.db import get_session
from app.core.enums import BanKind, OnboardingStep, UserStatus
from app.core.providers import FakeProviders
from app.core.providers.firebase import FakeFirebaseKeys
from app.core.security import E164, decrypt_phone, hash_phone, hash_token
from app.main import close_resources, create_app
from app.modules.auth import firebase_store
from app.modules.auth.models import BannedIdentity, Session
from app.modules.notifications.models import NotificationPrefs
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.modules.wallet.models import Wallet
from tests.conftest import MakeUser
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL, session_for_the_app

pytestmark = pytest.mark.usefixtures("test_redis")

START = datetime(2026, 10, 4, 6, 30, tzinfo=UTC)
PROJECT = "velora-test"
PHONE = "+919812345678"
EXCHANGE = "/v1/auth/firebase"
INVALID = {
    "error": {
        "code": "FIREBASE_TOKEN_INVALID",
        "message": "That sign-in didn't work. Ask for a new code.",
    }
}
# Drop a claim from `_claims`.
DROP = object()


def _settings(**overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        **{
            "ENV": "local",
            "DATABASE_URL": TEST_DATABASE_URL,
            "REDIS_URL": TEST_REDIS_URL,
            "CORS_ORIGINS": "http://127.0.0.1:3000",
            **PUBLIC_TEST_KEYS,
            "AUTH_PHONE_PROVIDER": "firebase",
            "FIREBASE_PROJECT_ID": PROJECT,
            **overrides,
        },
    )


SETTINGS = _settings()


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


@pytest.fixture
async def client(
    db: AsyncSession, fake_providers: FakeProviders
) -> AsyncIterator[AsyncClient]:
    """An app on Path A, sharing the test's `db`, Google played by the fake."""
    async with _client_for(SETTINGS, fake_providers) as c:
        yield c


@pytest.fixture
def google(fake_providers: FakeProviders) -> FakeFirebaseKeys:
    return fake_providers.firebase_keys


def _claims(
    phone: str = PHONE, *, at: datetime = START, **changes: Any
) -> dict[str, Any]:
    """A phone sign-in's claims as Firebase writes them, at `at`."""
    now = int(at.timestamp())
    claims: dict[str, Any] = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "auth_time": now,
        "user_id": "firebase-uid-1",
        "sub": "firebase-uid-1",
        "iat": now,
        "exp": now + 3600,
        "phone_number": phone,
        "firebase": {"identities": {"phone": [phone]}, "sign_in_provider": "phone"},
    }
    for name, value in changes.items():
        if value is DROP:
            del claims[name]
        else:
            claims[name] = value
    return claims


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


async def _exchange(client: AsyncClient, token: str, **headers: str) -> Response:
    return await client.post(EXCHANGE, json={"id_token": token}, headers=headers)


async def _accounts(db: AsyncSession, phone: str = PHONE) -> int:
    """Accounts on this number: never the whole table, since other tests in
    the run commit users of their own."""
    phone_hash = hash_phone(E164(phone), SETTINGS)
    return int(
        await db.scalar(select(func.count()).where(User.phone_hash == phone_hash)) or 0
    )


async def _users(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(User)) or 0)


async def _sessions(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(Session)) or 0)


def _cookies(response: Response) -> dict[str, dict[str, str | bool]]:
    """Each Set-Cookie by name, with every attribute exactly as sent."""
    cookies: dict[str, dict[str, str | bool]] = {}
    for header in response.headers.get_list("set-cookie"):
        first, *rest = [part.strip() for part in header.split(";")]
        name, _, _value = first.partition("=")
        attributes: dict[str, str | bool] = {}
        for part in rest:
            key, sep, val = part.partition("=")
            attributes[key.lower()] = val if sep else True
        cookies[name] = attributes
    return cookies


# --- A valid token signs in, creating the account the first time -----------------


async def test_a_valid_token_creates_exactly_one_account_and_a_session(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)

    response = await _exchange(client, google.sign(_claims()))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "user"}
    assert body["user"]["onboarding_step"] == OnboardingStep.DOB.value
    assert await _accounts(db) == 1
    user = await db.scalar(
        select(User).where(User.phone_hash == hash_phone(E164(PHONE), SETTINGS))
    )
    assert user is not None and str(user.id) == body["user"]["id"]
    assert await db.get(Profile, user.id) is not None
    wallet = await db.get(Wallet, user.id)
    assert wallet is not None and wallet.balance == 0
    assert await db.get(NotificationPrefs, user.id) is not None
    [session] = (await db.scalars(select(Session))).all()
    assert (session.user_id, session.auth_time) == (user.id, START)


async def test_a_second_sign_in_finds_the_same_account(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)
    first = await _exchange(client, google.sign(_claims()))
    later = START + timedelta(seconds=1)
    clock.freeze(later)

    second = await _exchange(client, google.sign(_claims(at=later)))

    assert second.status_code == 200
    assert second.json()["user"]["id"] == first.json()["user"]["id"]
    assert await _accounts(db) == 1
    assert await _sessions(db) == 2


async def test_the_number_is_the_account_whatever_firebase_calls_the_user(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    """Firebase's user ID changes if its user is ever deleted (P-39); the
    phone number, as on Path B, is what finds the account."""
    clock.freeze(START)
    first = await _exchange(client, google.sign(_claims()))
    later = START + timedelta(seconds=1)
    clock.freeze(later)

    second = await _exchange(
        client,
        google.sign(_claims(at=later, sub="firebase-uid-2", user_id="firebase-uid-2")),
    )

    assert second.json()["user"]["id"] == first.json()["user"]["id"]


async def test_both_cookies_are_set_exactly_as_path_b_sets_them(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)

    cookies = _cookies(await _exchange(client, google.sign(_claims())))

    thirty_days = str(30 * 24 * 60 * 60)
    assert cookies == {
        "refresh_local": {
            "httponly": True,
            "max-age": thirty_days,
            "path": "/v1/auth",
            "samesite": "lax",
            "secure": True,
        },
        "csrf_local": {
            "max-age": thirty_days,
            "path": "/",
            "samesite": "lax",
            "secure": True,
        },
    }


async def test_the_used_token_is_kept_as_its_hash_until_it_would_expire(
    db: AsyncSession,
    client: AsyncClient,
    google: FakeFirebaseKeys,
    clock: ModuleType,
    test_redis: Redis,
) -> None:
    clock.freeze(START)
    claims = _claims(exp=int(START.timestamp()) + 1800)
    token = google.sign(claims)

    await _exchange(client, token)

    keys = [
        key.decode()
        async for key in test_redis.scan_iter(match=f"{firebase_store.KEY_PREFIX}*")
    ]
    assert keys == [firebase_store.used_key(hash_token(token))]
    assert hash_token(token) == hashlib.sha256(token.encode()).hexdigest()
    assert 1795 <= await test_redis.ttl(keys[0]) <= 1800
    assert await test_redis.get(keys[0]) == b"1"


# --- Every refused token is the same 401 (06-TESTING 16) -----------------------


def _other_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _hs256_with_the_public_key(google: FakeFirebaseKeys) -> str:
    """The algorithm-confusion attack: HMAC-sign with Google's public key as
    the secret, hoping a verifier takes the key it was handed for either."""
    from app.core.providers.firebase import _fake_signing_key

    public = (
        _fake_signing_key()
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    header = _b64(
        json.dumps({"alg": "HS256", "kid": google.KID, "typ": "JWT"}).encode()
    )
    payload = _b64(json.dumps(_claims()).encode())
    signature = hmac.new(
        public, f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def _changed_payload(google: FakeFirebaseKeys) -> str:
    """A real token for one number, its payload swapped for another's."""
    header, _, signature = google.sign(_claims()).split(".")
    payload = _b64(json.dumps(_claims("+919800000001")).encode())
    return f"{header}.{payload}.{signature}"


NOW = int(START.timestamp())
TokenFor = Callable[[FakeFirebaseKeys], str]
REFUSED: dict[str, TokenFor] = {
    "signed by a key Google never published": lambda g: g.sign(
        _claims(), key=_other_key()
    ),
    "a key ID Google doesn't list": lambda g: g.sign(_claims(), kid="someone-elses"),
    "no key ID": lambda g: jwt.encode(
        _claims(),
        _other_key(),
        algorithm="RS256",
    ),
    "alg none": lambda g: jwt.encode(
        _claims(), "", algorithm="none", headers={"kid": g.KID}
    ),
    "HS256 with Google's public key as its secret": _hs256_with_the_public_key,
    "a changed payload": _changed_payload,
    "expired": lambda g: g.sign(_claims(exp=NOW)),
    "expired a while ago": lambda g: g.sign(
        _claims(iat=NOW - 3700, auth_time=NOW - 120, exp=NOW - 100)
    ),
    "issued in the future": lambda g: g.sign(_claims(iat=NOW + 31)),
    "signed in in the future": lambda g: g.sign(_claims(auth_time=NOW + 31)),
    "a sign-in older than five minutes": lambda g: g.sign(_claims(auth_time=NOW - 301)),
    "another project's audience": lambda g: g.sign(_claims(aud="someone-else")),
    "an audience list holding ours": lambda g: g.sign(
        _claims(aud=[PROJECT, "someone-else"])
    ),
    "another project's issuer": lambda g: g.sign(
        _claims(iss="https://securetoken.google.com/someone-else")
    ),
    "an issuer that only starts like ours": lambda g: g.sign(
        _claims(iss=f"https://securetoken.google.com/{PROJECT}x")
    ),
    "no subject": lambda g: g.sign(_claims(sub=DROP)),
    "an empty subject": lambda g: g.sign(_claims(sub="")),
    "a subject over 128 characters": lambda g: g.sign(_claims(sub="u" * 129)),
    "no expiry": lambda g: g.sign(_claims(exp=DROP)),
    "no sign-in time": lambda g: g.sign(_claims(auth_time=DROP)),
    "an expiry that isn't whole seconds": lambda g: g.sign(_claims(exp=NOW + 3600.5)),
    "an expiry that is true": lambda g: g.sign(_claims(exp=True)),
    "no phone number": lambda g: g.sign(_claims(phone_number=DROP)),
    "an empty phone number": lambda g: g.sign(_claims(phone_number="")),
    "signed in by email and password": lambda g: g.sign(
        _claims(firebase={"identities": {}, "sign_in_provider": "password"})
    ),
    "signed in anonymously": lambda g: g.sign(
        _claims(firebase={"identities": {}, "sign_in_provider": "anonymous"})
    ),
    "a custom token's sign-in": lambda g: g.sign(
        _claims(firebase={"identities": {}, "sign_in_provider": "custom"})
    ),
    "no firebase claim": lambda g: g.sign(_claims(firebase=DROP)),
    "not a token at all": lambda g: "not-a-token",
    "three dots of nothing": lambda g: "..",
}


@pytest.mark.critical
@pytest.mark.parametrize("case", list(REFUSED))
async def test_a_refused_token_gets_one_answer_and_no_account(
    db: AsyncSession,
    client: AsyncClient,
    google: FakeFirebaseKeys,
    clock: ModuleType,
    case: str,
) -> None:
    clock.freeze(START)

    response = await _exchange(client, REFUSED[case](google))

    assert response.status_code == 401
    assert response.json() == INVALID
    assert "set-cookie" not in response.headers
    assert await _accounts(db) == 0
    assert await _accounts(db, "+919800000001") == 0
    assert await _sessions(db) == 0


async def test_a_token_one_second_from_expiry_still_signs_in(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)

    response = await _exchange(client, google.sign(_claims(exp=NOW + 1)))

    assert response.status_code == 200


async def test_expiry_and_the_five_minutes_are_read_from_our_clock(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    """Minted at START, presented exactly five minutes on: still fresh. A
    second later it isn't. Only `core.clock` moved (rule 7)."""
    clock.freeze(START)
    on_time, late = google.sign(_claims()), google.sign(_claims(user_id="x"))

    clock.freeze(START + timedelta(minutes=5))
    assert (await _exchange(client, on_time)).status_code == 200
    clock.freeze(START + timedelta(minutes=5, seconds=1))
    response = await _exchange(client, late)

    assert response.status_code == 401
    assert response.json() == INVALID


async def test_googles_clock_may_run_up_to_thirty_seconds_ahead(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)

    response = await _exchange(
        client, google.sign(_claims(iat=NOW + 30, auth_time=NOW + 30))
    )

    assert response.status_code == 200


# --- Used once (D-085) --------------------------------------------------------------


@pytest.mark.critical
async def test_a_token_signs_in_once(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)
    token = google.sign(_claims())

    first = await _exchange(client, token)
    again = await _exchange(client, token)

    assert first.status_code == 200
    assert again.status_code == 401
    assert again.json() == INVALID
    assert "set-cookie" not in again.headers
    assert await _sessions(db) == 1


async def test_a_token_refused_for_its_number_is_not_spent(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    """Refused before it was used: the same answer again, not "already used"."""
    clock.freeze(START)
    token = google.sign(_claims("+16505550100"))

    first = await _exchange(client, token)
    again = await _exchange(client, token)

    assert first.json() == again.json()
    assert again.json()["error"]["code"] == "PHONE_NOT_SUPPORTED"


# --- India only (D-035) ---------------------------------------------------------------


@pytest.mark.critical
@pytest.mark.parametrize("phone", ["+16505550100", "+447400123456", "+9779812345678"])
async def test_a_number_outside_india_never_creates_a_user(
    db: AsyncSession,
    client: AsyncClient,
    google: FakeFirebaseKeys,
    clock: ModuleType,
    phone: str,
) -> None:
    """Firebase's region policy refuses these before an SMS (India only); a
    token for one is refused here too, whatever made it."""
    clock.freeze(START)
    users_before = await _users(db)

    response = await _exchange(client, google.sign(_claims(phone)))

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "PHONE_NOT_SUPPORTED",
            "message": "Only Indian (+91) numbers can sign up for now.",
        }
    }
    assert "set-cookie" not in response.headers
    assert await _users(db) == users_before
    assert await _sessions(db) == 0


# --- Who may sign in: T-3.3's rules, unchanged (D-067, D-073) -------------------------


async def test_a_banned_number_gets_account_banned_and_no_account(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    """On Path A the banned person holds a real token, so the ban shows, as
    D-073 records: unlike Path B, where their codes just stop arriving."""
    clock.freeze(START)
    db.add(
        BannedIdentity(
            kind=BanKind.PHONE_HASH,
            value=hash_phone(E164(PHONE), SETTINGS),
            reason="underage",
        )
    )
    await db.flush()

    response = await _exchange(client, google.sign(_claims()))

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "ACCOUNT_BANNED", "message": "This account has been banned."}
    }
    assert "set-cookie" not in response.headers
    assert await _accounts(db) == 0
    assert await _sessions(db) == 0


@pytest.mark.parametrize(
    ("status", "code"),
    [(UserStatus.BANNED, "ACCOUNT_BANNED"), (UserStatus.FROZEN, "ACCOUNT_FROZEN")],
)
async def test_an_account_banned_or_frozen_by_status_cant_sign_in(
    db: AsyncSession,
    client: AsyncClient,
    google: FakeFirebaseKeys,
    clock: ModuleType,
    make_user: MakeUser,
    status: UserStatus,
    code: str,
) -> None:
    clock.freeze(START)
    user, _ = await make_user()
    user.status = status
    await db.flush()
    assert user.phone_enc is not None
    phone = decrypt_phone(user.phone_enc, SETTINGS)

    response = await _exchange(client, google.sign(_claims(phone)))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == code
    assert await _sessions(db) == 0


# --- Google's keys unreachable: an outage, not a bad token ------------------------------


async def test_google_unreachable_is_provider_unavailable_not_an_invalid_token(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)
    token = google.sign(_claims())
    google.unavailable = True

    response = await _exchange(client, token)

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "message": "We can't check sign-ins right now. Try again in a few minutes.",
        }
    }
    assert await _accounts(db) == 0
    # Not spent: once Google answers, the same token still signs in.
    google.unavailable = False
    assert (await _exchange(client, token)).status_code == 200


# --- The body ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [{}, {"id_token": ""}, {"id_token": "x" * 4097}, {"id_token": 42}],
    ids=["missing", "empty", "over 4096", "not a string"],
)
async def test_a_body_without_a_usable_token_is_a_validation_error(
    db: AsyncSession,
    client: AsyncClient,
    google: FakeFirebaseKeys,
    body: dict[str, Any],
) -> None:
    response = await client.post(EXCHANGE, json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert google.lookups == 0


# --- 10 an IP and 5 a phone an hour (02-ARCHITECTURE §12) -------------------------------


async def test_the_eleventh_exchange_from_one_ip_in_an_hour_is_refused(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    """Refused tokens count: the limit is on tries, not sign-ins."""
    clock.freeze(START)
    for _ in range(10):
        assert (await _exchange(client, "not-a-token")).status_code == 401

    refused = await _exchange(client, google.sign(_claims()))

    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "RATE_LIMITED"
    assert refused.json()["error"]["details"] == {"retry_after_s": 3600}
    assert await _accounts(db) == 0

    clock.freeze(START + timedelta(hours=1))
    assert (await _exchange(client, "not-a-token")).status_code == 401


async def test_the_ip_limit_reads_flys_header_never_x_forwarded_for(
    db: AsyncSession, fake_providers: FakeProviders, clock: ModuleType
) -> None:
    """D-056: the address Fly's proxy saw. A forged X-Forwarded-For escapes
    nothing; another Fly-Client-IP is another bucket."""
    clock.freeze(START)
    settings = _settings(CLIENT_IP_HEADER="Fly-Client-IP")
    async with _client_for(settings, fake_providers) as client:
        for _ in range(10):
            await _exchange(client, "x", **{"Fly-Client-IP": "203.0.113.7"})

        forged = await _exchange(
            client,
            "x",
            **{"Fly-Client-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.1"},
        )
        other = await _exchange(client, "x", **{"Fly-Client-IP": "203.0.113.8"})

    assert forged.status_code == 429
    assert other.status_code == 401


async def test_the_sixth_sign_in_for_one_phone_in_an_hour_is_refused(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    for second in range(5):
        at = START + timedelta(seconds=second)
        clock.freeze(at)
        assert (await _exchange(client, google.sign(_claims(at=at)))).status_code == 200
    at = START + timedelta(seconds=5)
    clock.freeze(at)

    refused = await _exchange(client, google.sign(_claims(at=at)))

    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "RATE_LIMITED"
    assert await _sessions(db) == 5


async def test_replaying_a_token_doesnt_count_against_its_number(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    """Refused as used before the phone's limit is counted, so replaying
    someone's token can't lock them out of signing in."""
    clock.freeze(START)
    token = google.sign(_claims())
    assert (await _exchange(client, token)).status_code == 200
    for _ in range(4):
        assert (await _exchange(client, token)).status_code == 401
    later = START + timedelta(seconds=1)
    clock.freeze(later)

    response = await _exchange(client, google.sign(_claims(at=later)))

    assert response.status_code == 200


# --- Served only where AUTH_PHONE_PROVIDER is firebase (rule 16, D-085) -----------------


@pytest.mark.parametrize("provider", ["fake", "msg91", "provider-named-in-2031"])
async def test_no_other_provider_serves_the_exchange(
    db: AsyncSession, fake_providers: FakeProviders, clock: ModuleType, provider: str
) -> None:
    """A name nobody has listed gets nothing too, where a blacklist
    (`!= "msg91"`) would serve it (D-084's lesson)."""
    clock.freeze(START)
    settings = SETTINGS.model_copy(update={"AUTH_PHONE_PROVIDER": provider})

    async with _client_for(settings, fake_providers) as client:
        response = await _exchange(client, fake_providers.firebase_keys.sign(_claims()))

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not found."}}
    assert fake_providers.firebase_keys.lookups == 0
    assert await _accounts(db) == 0


# --- Rule 15 ------------------------------------------------------------------------------


async def test_no_token_number_or_hash_reaches_a_log_or_the_body(
    db: AsyncSession, client: AsyncClient, google: FakeFirebaseKeys, clock: ModuleType
) -> None:
    clock.freeze(START)
    claims = _claims()
    good = google.sign(claims)
    forged = google.sign(claims, key=_other_key())

    with capture_logs() as events:
        refused = await _exchange(client, forged)
        signed_in = await _exchange(client, good)
        replayed = await _exchange(client, good)

    assert [(e["event"], e.get("reason")) for e in events] == [
        ("firebase_token_refused", "signature"),
        ("firebase_token_refused", "reused"),
    ]
    text = "\n".join(
        [refused.text, signed_in.text, replayed.text, *(json.dumps(e) for e in events)]
    )
    national = PHONE.removeprefix("+91")
    secrets = [
        good,
        forged,
        *good.split("."),
        hash_token(good),
        PHONE,
        national,
        hash_phone(E164(PHONE), SETTINGS),
        claims["sub"],
    ]
    assert [s for s in secrets if s in text] == []
