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


def test_invalid_env_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(ENV="staging-ish")


def test_env_flags() -> None:
    assert _settings(ENV="local").debug is True
    assert _settings(ENV="production").is_production is True
    assert _settings(ENV="production").debug is False
