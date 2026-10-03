"""Security primitives: phone numbers, access and refresh tokens, PINs, CSRF,
OTP codes.

Every primitive is a vetted library's (D-060): phonenumbers parses numbers,
`hmac` and `hashlib` hash, `secrets` draws tokens, PyJWT signs and checks access
tokens, argon2-cffi hashes PINs and cryptography's Fernet encrypts. What this
module adds is policy only: Indian mobiles only, which key does what, the
token's claims, expiry read from `core.clock` (rule 7), and exactly one accepted
set of argon2 parameters.

The keys are hex in `Settings`, checked at startup; outside local, the repo's
own test keys are refused (`config.PUBLIC_TEST_KEYS`). Nothing here logs a
phone number, a PIN or a token (rule 15), and no error message repeats one.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, NewType
from uuid import UUID

import jwt
import phonenumbers
import structlog
from argon2 import Parameters, PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

from app.core import clock
from app.core.config import Settings
from app.core.enums import Role
from app.core.errors import AppError

log = structlog.get_logger(__name__)


# --- Phone numbers (D-035, D-061) ---------------------------------------------

E164 = NewType("E164", str)
"""A number as `normalize_phone` returns it: `+91` and digits, nothing else."""

_INDIA = 91
_E164_INDIA = re.compile(r"\+91[0-9]+")
# Signing in sends an SMS, so only a number that can receive one signs in
# (D-070): an allowlist of types, so a type India adds later is refused until
# someone decides. FIXED_LINE_OR_MOBILE is libphonenumber saying it can't tell:
# much of the 7 and 8 series overlaps landline area codes, and refusing those
# would turn away real mobiles. Refused: FIXED_LINE, TOLL_FREE (1800), UAN (the
# 140 series), SHARED_COST (1860) and PREMIUM_RATE.
_SMS_CAPABLE = frozenset(
    {
        phonenumbers.PhoneNumberType.MOBILE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    }
)


def normalize_phone(raw: str) -> E164:
    """An Indian mobile number in E.164 (`+919876543210`), or why it isn't one.

    Takes what people type: spaces, dashes, a leading 0 or 91, Devanagari
    digits. A valid number from anywhere else is `PHONE_NOT_SUPPORTED` (D-035);
    anything that isn't a valid number, or carries an extension, is
    `VALIDATION_ERROR` on `phone`, and so is a valid Indian number that can't
    receive an SMS (D-070). No error repeats the number.
    """
    try:
        number = phonenumbers.parse(raw, "IN")
    except phonenumbers.NumberParseException:
        raise _not_a_phone_number() from None
    if not phonenumbers.is_valid_number(number) or number.extension:
        raise _not_a_phone_number()
    if number.country_code != _INDIA:
        raise AppError(
            "PHONE_NOT_SUPPORTED",
            "Only Indian (+91) numbers can sign up for now.",
            status=422,
        )
    if phonenumbers.number_type(number) not in _SMS_CAPABLE:
        raise _phone_problem("isn't a mobile number")
    return E164(phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164))


def hash_phone(phone: E164, settings: Settings) -> str:
    """The number's lookup key: HMAC-SHA256 keyed by `PHONE_PEPPER`, as hex.

    The same number always gives the same hash: that's how login finds the
    account and how `banned_identities` stops a banned number signing up again.
    A number formatted any other way would hash differently and miss both, so
    only `normalize_phone`'s output is accepted. `PHONE_PEPPER` never changes
    once a number is banned, since the ban keeps only this hash (D-061).
    """
    _require_e164(phone)
    pepper = bytes.fromhex(settings.PHONE_PEPPER)
    return hmac.new(pepper, phone.encode(), hashlib.sha256).hexdigest()


def encrypt_phone(phone: E164, settings: Settings) -> bytes:
    """The number encrypted here, in the API, so the database holds ciphertext.

    Fernet through MultiFernet: the first key in `PHONE_ENC_KEY` encrypts and
    every one decrypts, so adding a key is a config change (D-061). The time
    Fernet stamps into the token comes from `core.clock` (rule 7).
    """
    _require_e164(phone)
    now = int(clock.now().timestamp())
    return _phone_cipher(settings).encrypt_at_time(phone.encode(), now)


def decrypt_phone(token: bytes, settings: Settings) -> E164:
    """The number back. A wrong key or a changed byte raises `InvalidToken`: a
    fault of ours, never the client's, so it is left to become a 500."""
    return E164(_phone_cipher(settings).decrypt(token).decode())


def _phone_cipher(settings: Settings) -> MultiFernet:
    return MultiFernet(
        [
            Fernet(base64.urlsafe_b64encode(bytes.fromhex(key)))
            for key in settings.PHONE_ENC_KEY
        ]
    )


def _require_e164(phone: str) -> None:
    if not _E164_INDIA.fullmatch(phone):
        raise ValueError(
            "expected an Indian number in E.164, as normalize_phone returns it"
        )


def _not_a_phone_number() -> AppError:
    return _phone_problem("isn't a valid phone number")


def _phone_problem(problem: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "Some of the information sent was not valid.",
        status=400,
        details={"fields": [{"field": "phone", "problem": problem}]},
    )


# --- Access tokens (D-024, D-060) -----------------------------------------------

# 15 minutes (D-024). A constant beside its decision, never in app_config: a
# security value that a database write could change, with nothing failing,
# isn't one (D-060).
ACCESS_TOKEN_TTL = timedelta(minutes=15)
_JWT_ALGORITHM = "HS256"
# Exactly these (D-060, D-071): `auth_time` is when the session's family signed
# in, carried unchanged through every refresh.
_ACCESS_CLAIMS = ("sub", "role", "aud", "iat", "exp", "auth_time")
_jwt = jwt.PyJWT(options={"enforce_minimum_key_length": True})


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    role: Role
    expires_at: datetime
    auth_time: datetime


def make_access_token(
    user_id: UUID, role: Role, settings: Settings, *, auth_time: datetime
) -> str:
    """A signed JWT for `Authorization: Bearer`, good for 15 minutes.

    `aud` is the environment. Separate `JWT_SECRET`s already keep staging's
    tokens out of production; this keeps them out even if a secret is ever
    copied across (D-055's reasoning, D-060). `auth_time` is when the session's
    family signed in, OpenID Connect's claim for it: D-069's PIN reset reads it
    to know a sign-in is fresh, without a database read (D-071).
    """
    issued_at = clock.now()
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "aud": settings.ENV,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + ACCESS_TOKEN_TTL).timestamp()),
        "auth_time": int(auth_time.timestamp()),
    }
    return _jwt.encode(payload, _jwt_key(settings), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> AccessClaims:
    """The claims of a token we signed, for this environment, not yet expired.

    Anything else is `AUTH_REQUIRED`. PyJWT checks the signature, the algorithm
    (HS256 only), the audience and that every claim is present. Expiry is ours:
    PyJWT reads the wall clock, which rule 7 forbids and tests can't move. It is
    checked only after the signature, so `TOKEN_EXPIRED`, which the web answers
    by refreshing (T-3.10), never goes to a forged token.
    """
    try:
        payload = _jwt.decode(
            token,
            _jwt_key(settings),
            algorithms=[_JWT_ALGORITHM],
            audience=settings.ENV,
            options={
                "require": list(_ACCESS_CLAIMS),
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except jwt.InvalidTokenError:
        raise _auth_required() from None
    expires, auth_time = payload["exp"], payload["auth_time"]
    # Whole seconds: not a float, and not a bool, which is an int.
    if type(expires) is not int or type(auth_time) is not int:
        raise _auth_required()
    if clock.now().timestamp() >= expires:
        raise AppError("TOKEN_EXPIRED", "Your session has expired.", status=401)
    try:
        user_id = UUID(payload["sub"])
        role = Role(payload["role"])
    except (TypeError, ValueError):
        raise _auth_required() from None
    return AccessClaims(
        user_id=user_id,
        role=role,
        expires_at=datetime.fromtimestamp(expires, UTC),
        auth_time=datetime.fromtimestamp(auth_time, UTC),
    )


def _jwt_key(settings: Settings) -> bytes:
    return bytes.fromhex(settings.JWT_SECRET)


def _auth_required() -> AppError:
    return AppError("AUTH_REQUIRED", "Sign in to continue.", status=401)


# --- Refresh tokens and CSRF (D-024, D-054, D-055) ------------------------------

# 32 random bytes as unpadded urlsafe base64: 43 characters of [A-Za-z0-9_-],
# safe as a cookie value and as a header without quoting. Which cookie carries
# each, and its name and scope, are the cookie-setting tasks' (T-3.3, T-3.4).
_TOKEN_BYTES = 32


def new_refresh_token() -> str:
    """An opaque refresh token. The cookie carries it; the database keeps only
    `hash_token()` of it, so a database leak opens no session."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 of a refresh token, as hex: `sessions.token_hash`.

    Plain SHA-256 is enough because the token is 256 random bits: there is
    nothing to guess, so no salt or pepper adds anything. The same token always
    gives the same hash, which is how refresh finds its session.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def new_csrf() -> str:
    """The readable CSRF cookie's value, which the web sends back as `X-CSRF`."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def csrf_matches(sent: str | None, expected: str | None) -> bool:
    """Whether `X-CSRF` matches the CSRF cookie, compared in constant time.

    `hmac.compare_digest` takes as long however early the values differ, so the
    comparison can't be timed byte by byte. Missing or empty never matches, not
    even another empty value: a request with neither must fail. Compared as
    bytes, so a header with non-ASCII in it is a mismatch rather than a 500.
    """
    if not sent or not expected:
        return False
    return hmac.compare_digest(sent.encode(), expected.encode())


# --- PINs (D-012, D-062) ------------------------------------------------------------

# D-062: argon2id with 19 MiB of memory, 2 passes, 1 lane — OWASP's minimum.
# Measured on staging's EPYC: 18.4 ms a hash; RFC 9106's 64 MiB took 156.9 ms.
#
# WARNING: these are a decision, not a tuning knob. Lowering them weakens every
# PIN stored from then on, and nothing fails: a weaker hash verifies like any
# other. A slow test suite is never a reason to touch them; D-062 says how a
# test-only setting would be added instead (local only, opted into, refused by
# staging and production). Raising them buys nothing either: with CODE_PEPPER
# off the database, a database leak reveals no PIN at any cost, and a leak that
# takes the pepper too breaks a 4-digit PIN in minutes at any cost (3 at these,
# 26 at 64 MiB). The pepper is the protection, and memory is the limit: at
# 64 MiB, two at a time in each of two workers is 256 MiB of 512 MB. Changing
# them in either direction makes every stored PIN fail verify_pin until it is
# set again, so a change needs a migration plan.
PIN_HASH_PARAMETERS = Parameters(
    type=Type.ID,
    version=19,
    salt_len=16,
    hash_len=32,
    time_cost=2,
    memory_cost=19 * 1024,  # KiB
    parallelism=1,
)
_pin_hasher = PasswordHasher.from_parameters(PIN_HASH_PARAMETERS)
# Each hash holds 19 MiB while it runs, and two workers share a 512 MB machine,
# so a process runs at most this many at once; a burst queues instead (D-062).
_PIN_HASHES_AT_ONCE = 2
_pin_hash_slots = asyncio.Semaphore(_PIN_HASHES_AT_ONCE)


async def hash_pin(pin: str, settings: Settings) -> str:
    """A PIN's stored form: argon2id over an HMAC of it, keyed off the database.

    Without `CODE_PEPPER`, which never enters the database, a stored hash can't
    be tested against even one guess (D-062). Hashing runs in a thread: ~20 ms
    of it would otherwise stop the event loop (rule 7).
    """
    secret = _peppered_pin(pin, settings)
    async with _pin_hash_slots:
        return await asyncio.to_thread(_pin_hasher.hash, secret)


async def verify_pin(pin: str, stored: str, settings: Settings) -> bool:
    """Whether `pin` is the PIN `stored` was made from.

    Only D-062's exact parameters are accepted. A stored hash made with any
    others, weaker or stronger, is refused, where argon2-cffi alone would verify
    it. A refused or unreadable hash is logged by its parameters, never the PIN
    or the hash, and returns False, like a wrong PIN.
    """
    try:
        parameters = extract_parameters(stored)
    except InvalidHashError:
        log.warning("pin_hash_unreadable")
        return False
    if parameters != PIN_HASH_PARAMETERS:
        log.warning(
            "pin_hash_parameters_refused",
            type=parameters.type.name,
            version=parameters.version,
            memory_cost=parameters.memory_cost,
            time_cost=parameters.time_cost,
            parallelism=parameters.parallelism,
            hash_len=parameters.hash_len,
            salt_len=parameters.salt_len,
        )
        return False
    secret = _peppered_pin(pin, settings)
    async with _pin_hash_slots:
        try:
            return await asyncio.to_thread(_pin_hasher.verify, stored, secret)
        except (VerificationError, InvalidHashError):
            return False


# The short codes people type share CODE_PEPPER, each use under its own key
# derived from it, so a PIN's hash and an OTP's can never stand in for each
# other: "pin" for PINs, "otp" for sign-in codes (D-063). The labels carry no brand
# name, since renaming the brand must never change a key (rule 17).
CodePurpose = Literal["pin", "otp"]


def _code_key(settings: Settings, purpose: CodePurpose) -> bytes:
    expand = HKDFExpand(
        algorithm=hashes.SHA256(), length=32, info=f"{purpose}/v1".encode()
    )
    return expand.derive(bytes.fromhex(settings.CODE_PEPPER))


def _peppered_pin(pin: str, settings: Settings) -> bytes:
    return hmac.new(_code_key(settings, "pin"), pin.encode(), hashlib.sha256).digest()


# --- OTP codes, Path B (D-063, D-066) ------------------------------------------------

# Six digits (D-066): with 10 wrong codes a day allowed per phone, four would
# give a determined guesser about a 30% chance at one person's account in a
# year; six give about 0.4%.
OTP_DIGITS = 6
_PHONE_HASH = re.compile(r"[0-9a-f]{64}")


def new_otp_code() -> str:
    """A sign-in code: six digits from `secrets`, leading zeros kept."""
    return f"{secrets.randbelow(10**OTP_DIGITS):0{OTP_DIGITS}d}"


def hash_otp(phone_hash: str, code: str, settings: Settings) -> str:
    """A code's stored form: HMAC-SHA256 over the number's hash and the code,
    under CODE_PEPPER's `otp` key, as hex (D-063).

    Not argon2: on an unauthenticated endpoint that would let one cheap request
    cost us 19 MiB and ~18 ms. A code's protection is its 5 tries and 5 minutes;
    the pepper, kept off Redis and the database, means a leak of either reveals
    no code. The number's hash is in the message, so a code stored for one
    number never matches another's, and only `hash_phone`'s output is taken, so
    the message can't be read two ways.
    """
    if not _PHONE_HASH.fullmatch(phone_hash):
        raise ValueError("expected a phone hash, as hash_phone returns it")
    message = f"{phone_hash}:{code}".encode()
    return hmac.new(_code_key(settings, "otp"), message, hashlib.sha256).hexdigest()


def otp_matches(phone_hash: str, code: str, stored: str, settings: Settings) -> bool:
    """Whether `code` is the one `stored` was made from, compared in constant
    time."""
    expected = hash_otp(phone_hash, code, settings)
    return hmac.compare_digest(expected.encode(), stored.encode())
