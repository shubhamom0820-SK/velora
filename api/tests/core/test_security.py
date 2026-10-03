"""Security primitives (core/security.py, D-060 to D-063).

A round trip passes whether a primitive is configured well or badly, so each
property here is tested so that a deliberately weakened version fails: a salt
that never changes, parameters nobody checks, a comparison with `==`, expiry
read from the wall clock. Known answers were computed outside Python, with
`openssl` and `shasum`, so the code isn't checked against itself.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any
from uuid import UUID

import jwt
import phonenumbers
import pytest
from argon2 import Parameters, PasswordHasher, Type, extract_parameters, profiles
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from structlog.testing import capture_logs

from app.core import clock as clock_module
from app.core import security
from app.core.config import PUBLIC_TEST_KEYS, Settings
from app.core.enums import Role
from app.core.errors import AppError
from app.core.security import (
    E164,
    PIN_HASH_PARAMETERS,
    csrf_matches,
    decode_access_token,
    decrypt_phone,
    encrypt_phone,
    hash_otp,
    hash_phone,
    hash_pin,
    hash_token,
    make_access_token,
    new_csrf,
    new_otp_code,
    new_refresh_token,
    normalize_phone,
    otp_matches,
    verify_pin,
)
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL
from tests.keys import random_keys


def _settings(**keys: str) -> Settings:
    """Local settings on the repo's public test keys, any of them replaced."""
    return Settings(
        _env_file=None,
        ENV="local",
        DATABASE_URL=TEST_DATABASE_URL,
        REDIS_URL=TEST_REDIS_URL,
        **{**PUBLIC_TEST_KEYS, **keys},  # type: ignore[arg-type]
    )


SETTINGS = _settings()
INDIAN = E164("+919876543210")


def _expect_error(call: Callable[[], object]) -> AppError:
    with pytest.raises(AppError) as excinfo:
        call()
    return excinfo.value


# --- Phone numbers (D-035, D-061) ----------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        "+91 98765 43210",
        "9876543210",
        "09876543210",
        "919876543210",
        "0091 98765 43210",
        "+91-98765-43210",
        "(+91) 98765 43210",
        "९८७६५४३२१०",  # Devanagari digits, from a Hindi keyboard
    ],
)
def test_indian_numbers_however_typed_become_e164(typed: str) -> None:
    assert normalize_phone(typed) == INDIAN


@pytest.mark.parametrize(
    "foreign",
    [
        "+1 415 555 2671",  # US
        "+44 20 7946 0958",  # UK
        "+971 50 123 4567",  # UAE
        "+92 300 1234567",  # Pakistan
        "+977 984 1234567",  # Nepal
        "001 415 555 2671",  # the US again, dialled from India
    ],
)
def test_a_valid_number_from_elsewhere_is_not_supported(foreign: str) -> None:
    error = _expect_error(lambda: normalize_phone(foreign))

    assert (error.code, error.status) == ("PHONE_NOT_SUPPORTED", 422)
    assert error.message == "Only Indian (+91) numbers can sign up for now."
    assert error.details is None


@pytest.mark.parametrize(
    "junk",
    [
        "",
        "abc",
        "12345",
        "+91 12345",  # too short
        "+91 98765 432101",  # too long
        "+91 00000 00000",
        "98765 43210abc",  # phonenumbers reads letters as keypad digits
        "+91 98765 43210 ext. 12",  # an extension can't be texted
        "9" * 300,
    ],
)
def test_anything_but_a_valid_number_is_a_validation_error_on_phone(junk: str) -> None:
    error = _expect_error(lambda: normalize_phone(junk))

    assert (error.code, error.status) == ("VALIDATION_ERROR", 400)
    assert error.message == "Some of the information sent was not valid."
    assert error.details == {
        "fields": [{"field": "phone", "problem": "isn't a valid phone number"}]
    }


# D-070: signing in sends an SMS, so only an Indian number that can receive one
# signs in. libphonenumber 9.0.40 types each of these as the comment says.


@pytest.mark.parametrize(
    "cant_receive_sms",
    [
        "+91 22 2222 2222",  # a Mumbai landline: FIXED_LINE
        "011 2345 6789",  # a Delhi landline, typed with its trunk 0: FIXED_LINE
        "1800 123 4567",  # toll-free: TOLL_FREE
        "140 123 4567",  # the 140 series: UAN
        "+91 1860 123 4567",  # shared cost: SHARED_COST
        "+91 1861 123 456789",  # premium rate: PREMIUM_RATE
    ],
)
def test_an_indian_number_that_cant_receive_an_sms_is_refused(
    cant_receive_sms: str,
) -> None:
    error = _expect_error(lambda: normalize_phone(cant_receive_sms))

    assert (error.code, error.status) == ("VALIDATION_ERROR", 400)
    assert error.message == "Some of the information sent was not valid."
    assert error.details == {
        "fields": [{"field": "phone", "problem": "isn't a mobile number"}]
    }


def test_a_number_libphonenumber_cant_place_as_landline_or_mobile_signs_in() -> None:
    """Much of the 7 and 8 series overlaps landline area codes, and the library
    answers FIXED_LINE_OR_MOBILE: it can't tell. Refusing those would turn away
    real mobiles, so they're accepted (D-070). This is the library's own example
    of the type for India."""
    ambiguous = "+91 74104 10123"
    parsed = phonenumbers.parse(ambiguous, "IN")
    assert (
        phonenumbers.number_type(parsed)
        == phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE
    )

    assert normalize_phone(ambiguous) == "+917410410123"


def test_exactly_two_of_indias_number_types_sign_in() -> None:
    """Only these, checked over every type India's metadata has: a list of the
    types refused would wave through one nobody listed."""
    accepted = set()
    for type_ in vars(phonenumbers.PhoneNumberType).values():
        if not isinstance(type_, int):
            continue
        example = phonenumbers.example_number_for_type("IN", type_)
        if example is None:
            continue
        typed = phonenumbers.format_number(example, phonenumbers.PhoneNumberFormat.E164)
        try:
            normalize_phone(typed)
        except AppError:
            continue
        accepted.add(phonenumbers.number_type(example))

    assert accepted == {
        phonenumbers.PhoneNumberType.MOBILE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    }


def test_a_foreign_landline_is_not_supported_rather_than_not_a_mobile() -> None:
    error = _expect_error(lambda: normalize_phone("+44 20 7946 0958"))

    assert error.code == "PHONE_NOT_SUPPORTED"


def test_the_phone_hash_is_hmac_sha256_keyed_by_phone_pepper() -> None:
    # printf %s '+919876543210' | openssl dgst -sha256 -hmac pppppppppppppppppppppppppppppppp
    # (PHONE_PEPPER's test key is "70" x 32: the bytes of "p" x 32.) Pinned, too:
    # changing how numbers hash would orphan every account and unban every ban.
    known = "b6abc7c4fd16d1195a8a568aba1818a8ab17911e805421be43063bc5906779ba"

    assert hash_phone(INDIAN, SETTINGS) == known


def test_the_same_number_always_hashes_the_same() -> None:
    """The opposite of a salt, on purpose: the hash is how login finds the
    account and how a ban recognises the number."""
    typed_two_ways = {
        hash_phone(normalize_phone("+91 98765 43210"), SETTINGS),
        hash_phone(normalize_phone("098765-43210"), SETTINGS),
    }

    assert len(typed_two_ways) == 1


def test_another_pepper_gives_another_hash_and_no_pepper_isnt_used() -> None:
    other = _settings(PHONE_PEPPER=random_keys()["PHONE_PEPPER"])

    assert hash_phone(INDIAN, other) != hash_phone(INDIAN, SETTINGS)
    assert hash_phone(INDIAN, SETTINGS) != hashlib.sha256(INDIAN.encode()).hexdigest()


@pytest.mark.parametrize(
    "unnormalised", ["+91 98765 43210", "9876543210", "+14155552671", ""]
)
def test_only_normalize_phones_output_is_hashed_or_encrypted(unnormalised: str) -> None:
    """A number formatted any other way would hash differently and miss its
    account, and its ban."""
    with pytest.raises(ValueError, match="as normalize_phone returns it"):
        hash_phone(E164(unnormalised), SETTINGS)
    with pytest.raises(ValueError, match="as normalize_phone returns it"):
        encrypt_phone(E164(unnormalised), SETTINGS)


def test_a_phone_number_encrypts_and_decrypts() -> None:
    assert decrypt_phone(encrypt_phone(INDIAN, SETTINGS), SETTINGS) == INDIAN


def test_the_same_number_encrypts_differently_every_time() -> None:
    assert encrypt_phone(INDIAN, SETTINGS) != encrypt_phone(INDIAN, SETTINGS)


def test_another_key_cannot_decrypt() -> None:
    token = encrypt_phone(INDIAN, SETTINGS)
    other = _settings(PHONE_ENC_KEY=random_keys()["PHONE_ENC_KEY"])

    with pytest.raises(InvalidToken):
        decrypt_phone(token, other)


def test_one_changed_byte_is_refused() -> None:
    raw = bytearray(base64.urlsafe_b64decode(encrypt_phone(INDIAN, SETTINGS)))
    raw[30] ^= 1  # inside the ciphertext

    with pytest.raises(InvalidToken):
        decrypt_phone(base64.urlsafe_b64encode(bytes(raw)), SETTINGS)


def test_a_second_encryption_key_is_a_config_change() -> None:
    """MultiFernet (D-061): put a new key first, and old numbers still read."""
    old_key, new_key = PUBLIC_TEST_KEYS["PHONE_ENC_KEY"], random_keys()["PHONE_ENC_KEY"]
    written_before = encrypt_phone(INDIAN, SETTINGS)
    rotated = _settings(PHONE_ENC_KEY=f"{new_key},{old_key}")

    written_after = encrypt_phone(INDIAN, rotated)

    assert decrypt_phone(written_before, rotated) == INDIAN
    assert decrypt_phone(written_after, _settings(PHONE_ENC_KEY=new_key)) == INDIAN
    with pytest.raises(InvalidToken):  # the new key wrote it, not the old one
        decrypt_phone(written_after, SETTINGS)


def test_the_time_inside_the_token_comes_from_core_clock(clock: ModuleType) -> None:
    clock.freeze(datetime(2027, 5, 13, 9, 30, tzinfo=UTC))
    token = encrypt_phone(INDIAN, SETTINGS)
    fernet = Fernet(
        base64.urlsafe_b64encode(bytes.fromhex(PUBLIC_TEST_KEYS["PHONE_ENC_KEY"]))
    )

    assert fernet.extract_timestamp(token) == int(clock.now().timestamp())


# --- Access tokens (D-024, D-060) --------------------------------------------------

USER_ID = UUID("0b6e0e5e-1a7b-4c1e-9d2a-3f4b5c6d7e8f")
JWT_KEY = bytes.fromhex(PUBLIC_TEST_KEYS["JWT_SECRET"])
# One instant before the wall clock and one after it: expiry read from the wall
# clock instead of core.clock fails one way for each.
INSTANTS = [datetime(2020, 1, 1, tzinfo=UTC), datetime(2040, 1, 1, tzinfo=UTC)]


def _claims(**changes: Any) -> dict[str, Any]:
    issued = int(clock_module.now().timestamp())
    claims: dict[str, Any] = {
        "sub": str(USER_ID),
        "role": "user",
        "aud": "local",
        "iat": issued,
        "exp": issued + 900,
    }
    claims.update(changes)
    return {k: v for k, v in claims.items() if v is not None}


def _sign(
    claims: dict[str, Any], key: bytes = JWT_KEY, algorithm: str = "HS256"
) -> str:
    return jwt.encode(claims, key, algorithm=algorithm)


def _with_role_changed(token: str) -> str:
    """The same token with its payload edited after signing."""
    header, _payload, signature = token.split(".")
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["role"] = "admin"
    edited = base64.urlsafe_b64encode(json.dumps(claims).encode())
    return ".".join([header, edited.rstrip(b"=").decode(), signature])


def test_a_token_round_trips() -> None:
    claims = decode_access_token(
        make_access_token(USER_ID, Role.MODERATOR, SETTINGS), SETTINGS
    )

    assert claims.user_id == USER_ID
    assert claims.role is Role.MODERATOR


def test_a_token_carries_exactly_these_claims(clock: ModuleType) -> None:
    clock.freeze(datetime(2030, 6, 1, 12, 0, tzinfo=UTC))
    issued = int(clock.now().timestamp())

    token = make_access_token(USER_ID, Role.USER, SETTINGS)

    assert jwt.get_unverified_header(token) == {"alg": "HS256", "typ": "JWT"}
    assert jwt.decode(token, options={"verify_signature": False}) == {
        "sub": str(USER_ID),
        "role": "user",
        "aud": "local",
        "iat": issued,
        "exp": issued + 15 * 60,
    }


@pytest.mark.parametrize("issued_at", INSTANTS, ids=["past", "future"])
def test_a_token_lasts_fifteen_minutes_by_core_clock(
    clock: ModuleType, issued_at: datetime
) -> None:
    clock.freeze(issued_at)
    token = make_access_token(USER_ID, Role.USER, SETTINGS)

    clock.advance(timedelta(minutes=14, seconds=59))
    assert decode_access_token(token, SETTINGS).expires_at == issued_at + timedelta(
        minutes=15
    )

    clock.advance(timedelta(seconds=1))
    error = _expect_error(lambda: decode_access_token(token, SETTINGS))
    assert (error.code, error.status) == ("TOKEN_EXPIRED", 401)
    assert error.message == "Your session has expired."


FORGERIES: dict[str, Callable[[], str]] = {
    "payload edited after signing": lambda: _with_role_changed(
        make_access_token(USER_ID, Role.USER, SETTINGS)
    ),
    "signed with another secret": lambda: _sign(
        _claims(), key=bytes.fromhex(random_keys()["JWT_SECRET"])
    ),
    "alg none": lambda: jwt.encode(_claims(), "", algorithm="none"),  # "" is no key
    "HS512 with our own key": lambda: _sign(_claims(), algorithm="HS512"),
    "another environment's": lambda: _sign(_claims(aud="staging")),
    "no sub": lambda: _sign(_claims(sub=None)),
    "no role": lambda: _sign(_claims(role=None)),
    "no aud": lambda: _sign(_claims(aud=None)),
    "no iat": lambda: _sign(_claims(iat=None)),
    "no exp": lambda: _sign(_claims(exp=None)),
    "exp a float": lambda: _sign(_claims(exp=float(_claims()["exp"]))),
    "exp a bool": lambda: _sign(_claims(exp=True)),
    "sub not a user id": lambda: _sign(_claims(sub="not-a-uuid")),
    "role not a role": lambda: _sign(_claims(role="superuser")),
    "garbage": lambda: "not.a.token",
    "empty": lambda: "",
}


@pytest.mark.parametrize("forgery", FORGERIES)
def test_anything_but_our_own_token_is_auth_required(forgery: str) -> None:
    token = FORGERIES[forgery]()

    error = _expect_error(lambda: decode_access_token(token, SETTINGS))

    assert (error.code, error.status) == ("AUTH_REQUIRED", 401)
    assert error.message == "Sign in to continue."


@pytest.mark.parametrize(
    "forgery",
    ["signed with another secret", "another environment's"],
)
def test_an_expired_forgery_is_auth_required_not_token_expired(
    clock: ModuleType, forgery: str
) -> None:
    """TOKEN_EXPIRED sends the web to refresh (T-3.10); a forged token must
    never learn that it merely expired."""
    token = FORGERIES[forgery]()
    clock.freeze(clock.now() + timedelta(hours=1))

    error = _expect_error(lambda: decode_access_token(token, SETTINGS))

    assert error.code == "AUTH_REQUIRED"


# --- Refresh tokens and CSRF (D-024, D-054, D-055) -------------------------------

MAKERS = [new_refresh_token, new_csrf]


@pytest.mark.parametrize("make", MAKERS)
def test_tokens_are_32_bytes_and_safe_in_cookies_and_headers(
    make: Callable[[], str],
) -> None:
    token = make()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert len(base64.urlsafe_b64decode(token + "=")) == 32


@pytest.mark.parametrize("make", MAKERS)
def test_tokens_are_drawn_from_secrets(
    make: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn: list[int | None] = []
    real = secrets.token_urlsafe

    def spy(nbytes: int | None = None) -> str:
        drawn.append(nbytes)
        return real(nbytes)

    monkeypatch.setattr(secrets, "token_urlsafe", spy)
    make()

    assert drawn == [32]


@pytest.mark.parametrize("make", MAKERS)
def test_a_thousand_tokens_are_a_thousand_different_tokens(
    make: Callable[[], str],
) -> None:
    assert len({make() for _ in range(1000)}) == 1000


def test_the_refresh_token_hash_is_plain_sha256() -> None:
    # printf %s 'refresh-token-for-a-known-answer' | shasum -a 256
    known = "f7da8b37db89e4f1642a8b36544d191de1e6e31032f1e8b13c381ff442ab9a40"

    assert hash_token("refresh-token-for-a-known-answer") == known


def test_a_refresh_token_always_hashes_the_same_and_tokens_differ() -> None:
    token = new_refresh_token()

    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != hash_token(new_refresh_token())


def test_the_same_csrf_value_matches() -> None:
    value = new_csrf()

    assert csrf_matches(value, value) is True


@pytest.mark.parametrize("position", [0, 21, 42], ids=["first", "middle", "last"])
def test_one_changed_character_anywhere_is_a_mismatch(position: int) -> None:
    value = new_csrf()
    changed = (
        value[:position]
        + ("A" if value[position] != "A" else "B")
        + value[position + 1 :]
    )

    assert csrf_matches(changed, value) is False


def test_values_of_different_lengths_dont_match() -> None:
    value = new_csrf()

    assert csrf_matches(value[:-1], value) is False


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        ("", ""),
        (None, None),
        (None, ""),
        ("", None),
        ("x", ""),
        ("", "x"),
        (None, "x"),
        ("x", None),
    ],
)
def test_missing_or_empty_never_matches(sent: str | None, expected: str | None) -> None:
    """Above all, not empty against empty: a request with neither header nor
    cookie must fail."""
    assert csrf_matches(sent, expected) is False


def test_a_non_ascii_header_is_a_mismatch_not_an_error() -> None:
    assert csrf_matches("tökén", new_csrf()) is False


def test_the_comparison_is_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through `hmac.compare_digest`, not `==`.

    A timing test couldn't tell them apart here: over 43 characters the gap is
    nanoseconds under Python's own overhead, so it would pass against `==` and
    flake in CI. What fails against `==` is checking which comparison ran;
    compare_digest's constant time is CPython's documented guarantee.
    """
    compared: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        compared.append((a, b))
        return real(a, b)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    value = new_csrf()

    assert csrf_matches(value, value) is True
    assert compared == [(value.encode(), value.encode())]


# --- PINs (D-012, D-062) -------------------------------------------------------------

PIN = "4821"


def _stored_with(parameters: Parameters, pin: str = PIN) -> str:
    """A stored hash of the right PIN, peppered exactly as hash_pin peppers it,
    made with `parameters`: the only thing that differs is the parameters."""
    return PasswordHasher.from_parameters(parameters).hash(
        security._peppered_pin(pin, SETTINGS)
    )


def test_the_parameters_are_d062s() -> None:
    expected = Parameters(
        type=Type.ID,
        version=19,
        salt_len=16,
        hash_len=32,
        time_cost=2,
        memory_cost=19 * 1024,
        parallelism=1,
    )

    assert PIN_HASH_PARAMETERS == expected, (
        "PIN_HASH_PARAMETERS changed. They are D-062's decision: lowering them weakens "
        "every PIN stored from then on and nothing else fails, and any change makes "
        "every stored PIN fail verify_pin. A slow suite is fixed with a local-only "
        "test setting (D-062), never by changing these."
    )


async def test_a_new_hash_carries_exactly_those_parameters() -> None:
    assert extract_parameters(await hash_pin(PIN, SETTINGS)) == PIN_HASH_PARAMETERS


async def test_the_same_pin_hashes_differently_every_time() -> None:
    first = await hash_pin(PIN, SETTINGS)
    second = await hash_pin(PIN, SETTINGS)

    assert first != second
    assert await verify_pin(PIN, first, SETTINGS) is True
    assert await verify_pin(PIN, second, SETTINGS) is True


async def test_the_right_pin_verifies_and_a_wrong_one_doesnt() -> None:
    stored = await hash_pin(PIN, SETTINGS)

    assert await verify_pin(PIN, stored, SETTINGS) is True
    assert await verify_pin("4822", stored, SETTINGS) is False


async def test_a_database_leak_alone_cant_test_a_single_guess() -> None:
    """D-062's reason: CODE_PEPPER never enters the database."""
    stored = await hash_pin(PIN, SETTINGS)

    # argon2 of the PIN itself, which anyone holding only the database could try:
    with pytest.raises(VerifyMismatchError):
        PasswordHasher.from_parameters(PIN_HASH_PARAMETERS).verify(stored, PIN)
    # and under any other CODE_PEPPER, the right PIN is wrong:
    other = _settings(CODE_PEPPER=random_keys()["CODE_PEPPER"])
    assert await verify_pin(PIN, stored, other) is False


def test_pins_and_otp_codes_get_their_own_keys_from_code_pepper() -> None:
    # printf 'pin/v1\001' | openssl dgst -sha256 -hmac cccccccccccccccccccccccccccccccc
    # and the same with otp/v1: HKDF-Expand to one block (CODE_PEPPER's test key is
    # "63" x 32, the bytes of "c" x 32). Pinned: a change here makes every
    # stored PIN fail.
    assert security._code_key(SETTINGS, "pin").hex() == (
        "0d0d937e0c0f1bf92db44d11cc31c5e024bbe15dcd1bec99fc839d8f75c0db85"
    )
    assert security._code_key(SETTINGS, "otp").hex() == (
        "7bd8b02f6934fe931334472299769a7b9644a3c243bc53824119d0b3721f125c"
    )


WEAKER = {
    "less memory": replace(PIN_HASH_PARAMETERS, memory_cost=8 * 1024),
    "one pass": replace(PIN_HASH_PARAMETERS, time_cost=1),
    "a shorter hash": replace(PIN_HASH_PARAMETERS, hash_len=16),
    "a shorter salt": replace(PIN_HASH_PARAMETERS, salt_len=8),
    "argon2i": replace(PIN_HASH_PARAMETERS, type=Type.I),
    "argon2d": replace(PIN_HASH_PARAMETERS, type=Type.D),
    "argon2-cffi's CHEAPEST": profiles.CHEAPEST,
}
NOT_WEAKER = {
    "two lanes": replace(PIN_HASH_PARAMETERS, parallelism=2),
    "more memory": replace(PIN_HASH_PARAMETERS, memory_cost=64 * 1024),
    "argon2-cffi's default (RFC 9106)": profiles.RFC_9106_LOW_MEMORY,
}


@pytest.mark.parametrize("weakened", WEAKER)
async def test_a_hash_with_weakened_parameters_is_refused(weakened: str) -> None:
    stored = _stored_with(WEAKER[weakened])

    # argon2-cffi on its own verifies it: the parameters travel inside the hash.
    assert PasswordHasher().verify(stored, security._peppered_pin(PIN, SETTINGS))
    assert await verify_pin(PIN, stored, SETTINGS) is False


@pytest.mark.parametrize("other", NOT_WEAKER)
async def test_a_hash_with_any_other_parameters_is_refused_too(other: str) -> None:
    """Exactly D-062's set: raising the cost later needs a migration plan, not a
    silent second set."""
    stored = _stored_with(NOT_WEAKER[other])

    assert await verify_pin(PIN, stored, SETTINGS) is False


async def test_a_refused_hash_is_logged_by_its_parameters_alone() -> None:
    stored = _stored_with(profiles.CHEAPEST)

    with capture_logs() as logs:
        assert await verify_pin(PIN, stored, SETTINGS) is False

    assert logs == [
        {
            "event": "pin_hash_parameters_refused",
            "log_level": "warning",
            "type": "ID",
            "version": 19,
            "memory_cost": 8,
            "time_cost": 1,
            "parallelism": 1,
            "hash_len": 4,
            "salt_len": 8,
        }
    ]
    assert PIN not in str(logs)
    assert stored not in str(logs)


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "abc",
        "$2b$12$R9h/cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jWMUW",  # bcrypt
        "$argon2id$v=19$m=19456,t=2,p=1$",
        "$argon2id$v=19$m=19456,t=2,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaA",
    ],
    ids=["empty", "text", "bcrypt", "truncated", "garbled"],
)
async def test_an_unreadable_stored_hash_is_false_never_an_error(stored: str) -> None:
    assert await verify_pin(PIN, stored, SETTINGS) is False


async def test_hashing_leaves_the_event_loop_running() -> None:
    """In a thread: ~20 ms of argon2 on the loop would stall every request."""
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0)

    ticker = asyncio.create_task(tick())
    await asyncio.sleep(0)
    try:
        before = ticks
        stored = await hash_pin(PIN, SETTINGS)
        while_hashing = ticks - before
        before = ticks
        await verify_pin(PIN, stored, SETTINGS)
        while_verifying = ticks - before
    finally:
        ticker.cancel()

    assert while_hashing > 0
    assert while_verifying > 0


async def test_at_most_two_hashes_run_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each holds 19 MiB while it runs; ten at once must queue, not pile up."""
    lock = threading.Lock()
    running = most = 0
    real = security._pin_hasher

    def counted(work: Callable[[], Any]) -> Any:
        nonlocal running, most
        with lock:
            running += 1
            most = max(most, running)
        try:
            threading.Event().wait(0.02)  # long enough for the others to pile in
            return work()
        finally:
            with lock:
                running -= 1

    class CountingHasher:
        def hash(self, secret: bytes) -> str:
            return str(counted(lambda: real.hash(secret)))

        def verify(self, stored: str, secret: bytes) -> bool:
            return bool(counted(lambda: real.verify(stored, secret)))

    monkeypatch.setattr(security, "_pin_hasher", CountingHasher())
    stored = await asyncio.gather(*(hash_pin(PIN, SETTINGS) for _ in range(10)))
    await asyncio.gather(*(verify_pin(PIN, s, SETTINGS) for s in stored))

    assert most == 2


# --- OTP codes (D-063, D-066) ---------------------------------------------------------

PHONE_HASH = "b6abc7c4fd16d1195a8a568aba1818a8ab17911e805421be43063bc5906779ba"
CODE = "042917"


def test_a_code_is_six_digits_drawn_from_secrets_with_leading_zeros_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drawn: list[int] = []

    def fake_randbelow(n: int) -> int:
        drawn.append(n)
        return 42

    monkeypatch.setattr(secrets, "randbelow", fake_randbelow)

    assert new_otp_code() == "000042"
    assert drawn == [1_000_000]


def test_a_thousand_codes_are_all_six_digits() -> None:
    codes = [new_otp_code() for _ in range(1000)]

    assert all(re.fullmatch(r"[0-9]{6}", code) for code in codes)
    # 1,000 draws from a million collide about half a time on average.
    assert len(set(codes)) >= 995


def test_the_otp_hash_is_hmac_sha256_of_the_number_hash_and_code() -> None:
    # K=$(printf 'otp/v1\001' | openssl dgst -sha256 -hmac cccccccccccccccccccccccccccccccc)
    # printf '%s:%s' <PHONE_HASH> 042917 | openssl dgst -sha256 -mac HMAC -macopt hexkey:$K
    assert hash_otp(PHONE_HASH, CODE, SETTINGS) == (
        "1e3e2dd445aebcc396c5908f3230f6b22cdfa04ae56cf7c18cb575b0473ea5d6"
    )


def test_an_otp_hash_is_never_a_pin_hash_and_the_reverse() -> None:
    """D-063: one pepper, two labels, so neither use's hash stands in for the
    other's. The same message under the `pin` key (computed with openssl, as
    above, with pin/v1) is a different value, and the PIN's own HMAC of the
    same digits, which argon2 wraps, is another."""
    under_pin_label = "bb7b39eb13bdea579665b4efc6eb6ccb906b1ca0670ce55b3a92a22a2150aaaf"
    otp_hash = hash_otp(PHONE_HASH, CODE, SETTINGS)

    assert otp_hash != under_pin_label
    assert otp_hash != security._peppered_pin(CODE, SETTINGS).hex()
    assert not otp_matches(PHONE_HASH, CODE, under_pin_label, SETTINGS)


async def test_an_otp_hash_never_verifies_as_a_stored_pin_and_the_reverse() -> None:
    pin_hash = await hash_pin(CODE, SETTINGS)
    otp_hash = hash_otp(PHONE_HASH, CODE, SETTINGS)

    assert await verify_pin(CODE, otp_hash, SETTINGS) is False
    assert otp_matches(PHONE_HASH, CODE, pin_hash, SETTINGS) is False


def test_a_code_stored_for_one_number_never_matches_another() -> None:
    other = hash_phone(E164("+919812345678"), SETTINGS)
    stored = hash_otp(PHONE_HASH, CODE, SETTINGS)

    assert hash_otp(other, CODE, SETTINGS) != stored
    assert otp_matches(other, CODE, stored, SETTINGS) is False


def test_another_code_pepper_gives_another_otp_hash() -> None:
    other = _settings(CODE_PEPPER=random_keys()["CODE_PEPPER"])
    stored = hash_otp(PHONE_HASH, CODE, SETTINGS)

    assert otp_matches(PHONE_HASH, CODE, stored, other) is False


def test_the_right_code_matches_and_any_other_doesnt() -> None:
    stored = hash_otp(PHONE_HASH, CODE, SETTINGS)

    assert otp_matches(PHONE_HASH, CODE, stored, SETTINGS) is True
    for wrong in ("042918", "42917", "0429170", "", "tökén"):
        assert otp_matches(PHONE_HASH, wrong, stored, SETTINGS) is False
    assert otp_matches(PHONE_HASH, CODE, "", SETTINGS) is False


def test_the_otp_comparison_is_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    compared: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        compared.append((a, b))
        return real(a, b)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    stored = hash_otp(PHONE_HASH, CODE, SETTINGS)

    assert otp_matches(PHONE_HASH, CODE, stored, SETTINGS) is True
    assert compared == [(stored.encode(), stored.encode())]


@pytest.mark.parametrize(
    "not_a_phone_hash",
    ["+919876543210", PHONE_HASH.upper(), PHONE_HASH[:-1], PHONE_HASH + ":0"],
    ids=["a phone number", "capitals", "too short", "with a colon"],
)
def test_only_hash_phones_output_is_taken(not_a_phone_hash: str) -> None:
    with pytest.raises(ValueError, match="phone hash"):
        hash_otp(not_a_phone_hash, CODE, SETTINGS)
