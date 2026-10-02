"""Settings fail fast: a missing required variable must not reach a request."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.core.config import PUBLIC_TEST_KEYS, Settings
from tests.keys import random_keys

_ALL_VARS = [
    "ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "PHONE_PEPPER",
    "PHONE_ENC_KEY",
    "CODE_PEPPER",
    "CORS_ORIGINS",
    "COOKIE_DOMAIN",
    "CLIENT_IP_HEADER",
    "AUTH_PHONE_PROVIDER",
    "SMS_PROVIDER",
    "PAYMENTS_PROVIDER",
    "MODERATION_PROVIDER",
    "FACEMATCH_PROVIDER",
    "STORAGE_PROVIDER",
    "PUSH_PROVIDER",
]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """conftest seeds the environment for the app tests; these assert on the
    declared defaults, so the real environment must not leak in."""
    for name in _ALL_VARS:
        monkeypatch.delenv(name, raising=False)


_REQUIRED = {
    "ENV": "local",
    "DATABASE_URL": "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    **PUBLIC_TEST_KEYS,
}


# A real provider for every setting: what staging and production must name (D-045).
_REAL_PROVIDERS = {
    "AUTH_PHONE_PROVIDER": "firebase",
    "SMS_PROVIDER": "msg91",
    "PAYMENTS_PROVIDER": "razorpay",
    "MODERATION_PROVIDER": "sightengine",
    "FACEMATCH_PROVIDER": "rekognition",
    "STORAGE_PROVIDER": "s3",
    "PUSH_PROVIDER": "webpush",
}
# What staging and production must set beyond that: Redis over TLS, the header
# the proxy puts the client's IP in (D-056), and keys that aren't the repo's
# public test keys (D-060).
_DEPLOYED = {
    **_REAL_PROVIDERS,
    "REDIS_URL": "rediss://default:x@redis.example:6379/0",
    "CLIENT_IP_HEADER": "Fly-Client-IP",
    **random_keys(),
}


def _settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **overrides})  # type: ignore[arg-type]


@pytest.mark.parametrize("missing", sorted(_REQUIRED))
def test_missing_required_var_raises(missing: str) -> None:
    values = {k: v for k, v in _REQUIRED.items() if k != missing}

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, **values)  # type: ignore[arg-type]

    assert missing in str(excinfo.value)


def test_cors_origins_parses_a_comma_list() -> None:
    settings = _settings(CORS_ORIGINS="http://localhost:3000, https://velora.app")

    assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://velora.app"]


def test_cors_origins_defaults_to_empty() -> None:
    assert _settings().CORS_ORIGINS == []


def test_providers_default_to_fake() -> None:
    settings = _settings()

    assert settings.AUTH_PHONE_PROVIDER == "fake"
    assert settings.SMS_PROVIDER == "fake"
    assert settings.PAYMENTS_PROVIDER == "fake"
    assert settings.MODERATION_PROVIDER == "fake"
    assert settings.FACEMATCH_PROVIDER == "fake"
    assert settings.STORAGE_PROVIDER == "fake"
    assert settings.PUSH_PROVIDER == "fake"


def test_invalid_env_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(ENV="staging-ish")


def test_env_flags() -> None:
    assert _settings(ENV="local").debug is True
    assert _settings(ENV="production", **_DEPLOYED).is_production is True
    assert _settings(ENV="production", **_DEPLOYED).debug is False


# --- Fakes run only where ENV is local (D-045) ---------------------------------


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("provider", sorted(_REAL_PROVIDERS))
def test_a_fake_provider_outside_local_refuses_to_start(
    env: str, provider: str
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _settings(ENV=env, **{**_DEPLOYED, provider: "fake"})

    message = str(excinfo.value)
    assert f"ENV={env} cannot use fake providers ({provider})" in message
    assert "D-045" in message


def test_every_fake_is_named_at_once() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _settings(ENV="production")  # all seven default to fake

    assert "(" + ", ".join(_REAL_PROVIDERS) + ")" in str(excinfo.value)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_real_providers_start_outside_local(env: str) -> None:
    settings = _settings(ENV=env, **_DEPLOYED)

    assert all(getattr(settings, name) != "fake" for name in _REAL_PROVIDERS)


def test_local_may_use_fakes_and_real_providers() -> None:
    assert _settings(ENV="local").PAYMENTS_PROVIDER == "fake"
    assert _settings(ENV="local", **_REAL_PROVIDERS).PAYMENTS_PROVIDER == "razorpay"


# --- URLs: a wrong scheme fails at the settings check, and no value is echoed --


def _error(**overrides: str) -> str:
    with pytest.raises(ValidationError) as excinfo:
        _settings(**overrides)
    return str(excinfo.value)


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        (
            "DATABASE_URL",
            "postgresql://velora:hunter2@db.example:5432/velora",
            "postgresql+asyncpg://",
        ),
        (
            "DATABASE_URL",
            "mysql://velora:hunter2@db.example/velora",
            "postgresql+asyncpg://",
        ),
        # T-1.22's failure: the command that should have set REDIS_URL, as its value.
        (
            "REDIS_URL",
            "printf 'REDIS_URL=%s' hunter2 | fly secrets import",
            "rediss://",
        ),
        ("REDIS_URL", "https://default:hunter2@redis.example", "rediss://"),
        # T-1.22's second failure: a closing quote pasted with the URL.
        (
            "REDIS_URL",
            'rediss://default:hunter2@redis.example:6379"',
            "valid Redis URL",
        ),
        (
            "REDIS_URL",
            "rediss://default:hunter2@redis.example:6379 ",
            "valid Redis URL",
        ),
        (
            "DATABASE_URL",
            'postgresql+asyncpg://u:hunter2@db.example:5432"/velora',
            "valid database URL",
        ),
        (
            "DATABASE_URL",
            "postgresql+asyncpg://u:hunter2@db.example:54x2/velora",
            "valid database URL",
        ),
    ],
)
def test_a_url_with_the_wrong_scheme_is_named_but_not_echoed(
    name: str, value: str, expected: str
) -> None:
    message = _error(**{name: value})

    assert name in message
    assert expected in message
    assert "hunter2" not in message
    assert "input_value" not in message


@pytest.mark.parametrize("env", ["staging", "production"])
def test_plain_redis_is_refused_outside_local(env: str) -> None:
    message = _error(
        ENV=env,
        **{**_DEPLOYED, "REDIS_URL": "redis://default:hunter2@redis.example:6379/0"},
    )

    assert f"ENV={env} needs REDIS_URL to use rediss://" in message
    assert "hunter2" not in message


def test_plain_redis_is_fine_locally_and_tls_everywhere() -> None:
    assert _settings(ENV="local").REDIS_URL.startswith("redis://")
    assert _settings(ENV="production", **_DEPLOYED).REDIS_URL.startswith("rediss://")


def test_no_validation_error_echoes_a_value() -> None:
    """hide_input_in_errors: even an unrelated error never prints what was given."""
    message = _error(ENV="staging-ish", JWT_SECRET="hunter2-jwt")

    assert "ENV" in message
    assert "hunter2-jwt" not in message
    assert "input_value" not in message


# --- Per-IP limits read the proxy's header outside local (D-056) ---------------


@pytest.mark.parametrize("env", ["staging", "production"])
def test_no_client_ip_header_outside_local_refuses_to_start(env: str) -> None:
    message = _error(ENV=env, **{**_DEPLOYED, "CLIENT_IP_HEADER": ""})

    assert f"ENV={env} needs CLIENT_IP_HEADER (Fly-Client-IP on Fly)" in message
    assert "X-Forwarded-For is written by the client" in message
    assert "D-056" in message


def test_local_may_read_the_socket_or_a_header() -> None:
    assert _settings(ENV="local").CLIENT_IP_HEADER == ""
    assert (
        _settings(ENV="local", CLIENT_IP_HEADER="Fly-Client-IP").CLIENT_IP_HEADER
        == "Fly-Client-IP"
    )


# --- Keys are checked for shape, everywhere (D-060) -----------------------------

_A64 = "a" * 64
# Not hex, but recognisable, so a test can prove the value is never echoed.
_SECRETISH = "hunter2" + "a" * 57


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("JWT_SECRET", "x", "at least 128 hex characters (64 bytes)"),
        ("JWT_SECRET", "a" * 126, "at least 128 hex characters (64 bytes)"),
        ("JWT_SECRET", "a" * 129, "at least 128 hex characters (64 bytes)"),
        ("JWT_SECRET", _SECRETISH * 2, "openssl rand -hex 64"),
        ("JWT_SECRET", "a" * 128 + " ", "check for stray quotes or spaces"),
        ("PHONE_PEPPER", "a" * 63, "exactly 64 hex characters (32 bytes)"),
        ("PHONE_PEPPER", "a" * 65, "exactly 64 hex characters (32 bytes)"),
        ("PHONE_PEPPER", _SECRETISH, "openssl rand -hex 32"),
        ("PHONE_PEPPER", '"' + "a" * 62 + '"', "check for stray quotes or spaces"),
        ("CODE_PEPPER", "a" * 63, "exactly 64 hex characters (32 bytes)"),
        ("CODE_PEPPER", _SECRETISH, "openssl rand -hex 32"),
        ("PHONE_ENC_KEY", "", "one or more keys of exactly 64 hex characters"),
        ("PHONE_ENC_KEY", _SECRETISH, "one or more keys of exactly 64 hex characters"),
        ("PHONE_ENC_KEY", f"{_A64}, {'b' * 64}", "with no spaces"),
        ("PHONE_ENC_KEY", f"{_A64},,{'b' * 64}", "with no spaces"),
        ("PHONE_ENC_KEY", f"{_A64},", "with no spaces"),
        ("PHONE_ENC_KEY", f"{_A64},{_A64}", "lists the same key more than once"),
        # The same bytes in capitals are the same key.
        (
            "PHONE_ENC_KEY",
            f"{_A64},{_A64.upper()}",
            "lists the same key more than once",
        ),
    ],
)
def test_a_badly_shaped_key_is_named_but_not_echoed(
    name: str, value: str, expected: str
) -> None:
    message = _error(**{name: value})

    assert name in message
    assert expected in message
    assert "hunter2" not in message
    assert "input_value" not in message


def test_well_shaped_keys_are_accepted() -> None:
    settings = _settings(
        JWT_SECRET="AB" * 96,  # longer than the minimum, and in capitals
        PHONE_PEPPER="0f" * 32,
        CODE_PEPPER="F0" * 32,
        PHONE_ENC_KEY=f"{'1' * 64},{'2' * 64}",
    )

    assert settings.JWT_SECRET == "AB" * 96
    # Newest first: the first encrypts, both decrypt (D-061).
    assert settings.PHONE_ENC_KEY == ("1" * 64, "2" * 64)


# --- The repo's public test keys work only where ENV is local (D-060) -----------


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("name", sorted(PUBLIC_TEST_KEYS))
def test_a_public_test_key_outside_local_refuses_to_start(env: str, name: str) -> None:
    message = _error(ENV=env, **{**_DEPLOYED, name: PUBLIC_TEST_KEYS[name]})

    assert f"ENV={env} cannot use the repo's public test keys ({name})" in message
    assert "anyone who can read the repo" in message
    assert "D-060" in message


def test_every_public_test_key_is_named_at_once() -> None:
    message = _error(ENV="production", **{**_DEPLOYED, **PUBLIC_TEST_KEYS})

    assert "(JWT_SECRET, PHONE_PEPPER, PHONE_ENC_KEY, CODE_PEPPER)" in message


def test_a_public_test_key_in_capitals_is_still_refused() -> None:
    message = _error(
        ENV="staging",
        **{**_DEPLOYED, "JWT_SECRET": PUBLIC_TEST_KEYS["JWT_SECRET"].upper()},
    )

    assert "public test keys (JWT_SECRET)" in message


def test_the_public_encryption_key_is_refused_as_an_older_key_too() -> None:
    keys = f"{random_keys()['PHONE_ENC_KEY']},{PUBLIC_TEST_KEYS['PHONE_ENC_KEY']}"

    message = _error(ENV="staging", **{**_DEPLOYED, "PHONE_ENC_KEY": keys})

    assert "public test keys (PHONE_ENC_KEY)" in message


def test_local_runs_on_the_public_test_keys() -> None:
    settings = _settings(ENV="local")

    assert settings.JWT_SECRET == PUBLIC_TEST_KEYS["JWT_SECRET"]
    assert settings.PHONE_ENC_KEY == (PUBLIC_TEST_KEYS["PHONE_ENC_KEY"],)


def test_ci_publishes_exactly_the_refused_keys() -> None:
    """CI's own keys are the ones staging and production refuse, and a YAML
    parser reads each back as the string written.

    If ci.yml carried a key that isn't in PUBLIC_TEST_KEYS, a copy of it on
    staging would start without complaint: the refusal only knows these. And
    run 37078451050 showed what the file's text doesn't: GitHub read the
    unquoted, all-digit PHONE_PEPPER as the number 7.07070707070707E+63, and
    settings refused it. So this parses the file instead of matching it, which
    also catches `yes`, a leading zero, `0x…` or a folded scalar.

    Keep both halves. PyYAML is YAML 1.1 and GitHub's parser isn't exactly that
    (they disagree on yes and no, for one), so this proves that a YAML parser
    makes a string of each value, not that GitHub's does. Quoting the values in
    ci.yml is what makes every parser agree. Together they're sound; either
    alone isn't, so neither is redundant.
    """
    ci = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    env = yaml.safe_load(ci.read_text())["env"]

    for name, expected in PUBLIC_TEST_KEYS.items():
        value = env.get(name)
        assert isinstance(value, str), (
            f"{name} parses as {type(value).__name__}, not a string: quote it"
        )
        assert re.fullmatch(r"[0-9a-f]+", value), f"{name} isn't lowercase hex"
        assert len(value) == len(expected), f"{name} is {len(value)} characters"
        assert value == expected, f"{name} isn't the refused test key"
