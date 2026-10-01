"""Settings fail fast: a missing required variable must not reach a request."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_ALL_VARS = [
    "ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "PHONE_PEPPER",
    "PHONE_ENC_KEY",
    "CORS_ORIGINS",
    "COOKIE_DOMAIN",
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
    "JWT_SECRET": "x",
    "PHONE_PEPPER": "x",
    "PHONE_ENC_KEY": "x",
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
# What staging and production must set beyond that: Redis over TLS.
_DEPLOYED = {**_REAL_PROVIDERS, "REDIS_URL": "rediss://default:x@redis.example:6379/0"}


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
