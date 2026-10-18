"""Settings fail fast: a missing required variable must not reach a request."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.core.config import PUBLIC_TEST_KEYS, Settings
from tests.gce import gce_env
from tests.keys import r2_settings, random_keys, vapid_settings

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
    "FIREBASE_PROJECT_ID",
    "SMS_PROVIDER",
    "SMS_LOCAL_ALLOWED_TO",
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
    "FACEMATCH_PROVIDER": "sface",
    "STORAGE_PROVIDER": "s3",
    "PUSH_PROVIDER": "webpush",
}
# Path A's project, which firebase needs wherever it runs (D-085).
_FIREBASE = {"FIREBASE_PROJECT_ID": "velora-test"}
# What staging and production must set beyond that: Redis over TLS, the header
# the proxy puts the client's IP in (D-056), and keys that aren't the repo's
# public test keys (D-060).
_DEPLOYED = {
    **_REAL_PROVIDERS,
    **_FIREBASE,
    # What webpush needs (T-9.4).
    **vapid_settings(),
    # What s3 storage needs (T-4.1).
    **r2_settings(),
    "REDIS_URL": "rediss://default:x@redis.example:6379/0",
    "CLIENT_IP_HEADER": "Caddy-Client-IP",
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


def test_the_worker_polls_every_10_seconds_unless_told() -> None:
    """D-091: 10 seconds on Upstash Free; ARQ's own default is 0.5."""
    assert _settings().WORKER_POLL_DELAY_S == 10
    assert _settings(WORKER_POLL_DELAY_S="2.5").WORKER_POLL_DELAY_S == 2.5


@pytest.mark.parametrize("delay", ["0", "-1"])
def test_a_poll_delay_of_zero_or_less_is_refused(delay: str) -> None:
    with pytest.raises(ValidationError, match="WORKER_POLL_DELAY_S"):
        _settings(WORKER_POLL_DELAY_S=delay)


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
    assert (
        _settings(
            ENV="local",
            **_REAL_PROVIDERS,
            **_FIREBASE,
            **r2_settings(),
            **vapid_settings(),
        ).PAYMENTS_PROVIDER
        == "razorpay"
    )


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


# --- Locally, a real SMS provider texts only listed numbers (D-064, D-066) -----


def test_nobody_is_listed_by_default() -> None:
    assert _settings().SMS_LOCAL_ALLOWED_TO == ()


def test_listed_numbers_are_normalised_however_typed() -> None:
    settings = _settings(SMS_LOCAL_ALLOWED_TO="98765 43210, +91 98123-45678,")

    assert settings.SMS_LOCAL_ALLOWED_TO == ("+919876543210", "+919812345678")


@pytest.mark.parametrize(
    "listed",
    ["98765 43210,12345", "98765 43210,+44 20 7946 0958", "98765 43210,1800 123 4567"],
    ids=["not a number", "not Indian", "not a mobile"],
)
def test_a_listed_number_normalize_phone_refuses_stops_startup_unechoed(
    listed: str,
) -> None:
    message = _error(SMS_LOCAL_ALLOWED_TO=listed)

    assert "SMS_LOCAL_ALLOWED_TO" in message
    assert "entry 2 isn't an Indian mobile number" in message
    for typed in listed.split(","):
        assert typed.strip() not in message
    assert "9876543210" not in message


@pytest.mark.parametrize("env", ["staging", "production"])
def test_the_list_outside_local_refuses_to_start(env: str) -> None:
    message = _error(ENV=env, **{**_DEPLOYED, "SMS_LOCAL_ALLOWED_TO": "98765 43210"})

    assert f"ENV={env} cannot set SMS_LOCAL_ALLOWED_TO" in message
    assert "look like protection it isn't (D-066)" in message
    assert "9876543210" not in message


@pytest.mark.parametrize("env", ["staging", "production"])
def test_outside_local_an_empty_list_is_fine(env: str) -> None:
    assert _settings(ENV=env, **_DEPLOYED).SMS_LOCAL_ALLOWED_TO == ()


# --- Per-IP limits read the proxy's header outside local (D-056) ---------------


@pytest.mark.parametrize("env", ["staging", "production"])
def test_no_client_ip_header_outside_local_refuses_to_start(env: str) -> None:
    message = _error(ENV=env, **{**_DEPLOYED, "CLIENT_IP_HEADER": ""})

    assert f"ENV={env} needs CLIENT_IP_HEADER (Caddy-Client-IP behind Caddy" in message
    assert "X-Forwarded-For is written by the client" in message
    assert "D-056" in message


def test_local_may_read_the_socket_or_a_header() -> None:
    assert _settings(ENV="local").CLIENT_IP_HEADER == ""
    assert (
        _settings(ENV="local", CLIENT_IP_HEADER="Caddy-Client-IP").CLIENT_IP_HEADER
        == "Caddy-Client-IP"
    )


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("header", ["X-Forwarded-For", "X-E2E-Client-IP"])
def test_outside_local_only_caddys_header_is_read(env: str, header: str) -> None:
    """A header the client writes can't be configured where it would count
    (D-890): the E2E server's per-context address and X-Forwarded-For alike."""
    message = _error(ENV=env, **{**_DEPLOYED, "CLIENT_IP_HEADER": header})

    assert (
        f"ENV={env} reads the client's IP only from Caddy-Client-IP or "
        f"Fly-Client-IP, not {header}" in message
    )
    assert "is one the client can write" in message
    assert "D-890" in message


@pytest.mark.parametrize("env", ["staging", "production"])
def test_outside_local_caddys_header_is_read_in_any_case(env: str) -> None:
    for header in (
        "Caddy-Client-IP",
        "caddy-client-ip",
        "Fly-Client-IP",
        "FLY-CLIENT-IP",
    ):
        assert _settings(ENV=env, **{**_DEPLOYED, "CLIENT_IP_HEADER": header})


def test_local_may_read_the_e2e_servers_header() -> None:
    settings = _settings(ENV="local", CLIENT_IP_HEADER="X-E2E-Client-IP")

    assert settings.CLIENT_IP_HEADER == "X-E2E-Client-IP"


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


# --- Path A names its Firebase project (D-085) -----------------------------------


@pytest.mark.parametrize("env", ["local", "staging", "production"])
def test_firebase_without_a_project_refuses_to_start(env: str) -> None:
    """Every token would fail its audience check; better to fail here."""
    deployed = {} if env == "local" else _DEPLOYED
    with pytest.raises(ValidationError) as excinfo:
        _settings(
            ENV=env,
            **{
                **deployed,
                "AUTH_PHONE_PROVIDER": "firebase",
                "FIREBASE_PROJECT_ID": "",
            },
        )

    assert "AUTH_PHONE_PROVIDER=firebase needs FIREBASE_PROJECT_ID" in str(
        excinfo.value
    )


@pytest.mark.parametrize(
    "project",
    [
        "Velora-IC",  # capitals
        "velora-ic ",  # a stray space
        '"velora-ic"',  # stray quotes
        "velor",  # too short: six at least
        "9velora-ic",  # starts with a digit
        "velora-ic-",  # ends with a hyphen
        "v" * 31,  # too long: thirty at most
    ],
)
def test_a_malformed_project_is_named_but_not_echoed(project: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _settings(AUTH_PHONE_PROVIDER="firebase", FIREBASE_PROJECT_ID=project)

    message = str(excinfo.value)
    assert "FIREBASE_PROJECT_ID must be a Firebase project ID" in message
    assert project not in message


def test_a_firebase_project_id_is_accepted() -> None:
    settings = _settings(
        AUTH_PHONE_PROVIDER="firebase", FIREBASE_PROJECT_ID="velora-ic"
    )

    assert settings.FIREBASE_PROJECT_ID == "velora-ic"


@pytest.mark.parametrize("provider", ["fake", "msg91"])
def test_other_providers_need_no_firebase_project(provider: str) -> None:
    assert _settings(AUTH_PHONE_PROVIDER=provider).FIREBASE_PROJECT_ID == ""


# --- Staging's own settings, as infra/gce/staging.env sets them (T-3.3, P-49) ---


def test_stagings_csrf_cookie_reaches_its_web_and_never_production() -> None:
    """Parsed, not matched as text. The CSRF cookie's Domain must cover the
    staging web's host, the one CORS allows, so its pages can read it; and
    must sit under staging's name, so it never reaches production (D-055)."""
    env = gce_env("staging")
    domain = env["COOKIE_DOMAIN"]
    [origin] = env["CORS_ORIGINS"].split(",")
    web_host = urlsplit(origin).hostname or ""

    assert domain == "staging.veloraapp.co.in"
    assert web_host == domain or web_host.endswith("." + domain)
    assert domain.endswith(".veloraapp.co.in")


def test_stagings_env_block_passes_settings() -> None:
    """Everything staging.env sets, plus secrets shaped as Secret Manager holds
    them, starts: a value there that Settings refuses would stop the deploy."""
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app:x@db.example:5432/postgres",
        "REDIS_URL": "rediss://default:x@redis.example:6379/0",
        **random_keys(),
        # R2's token: in Secret Manager, never in the file (infra/STAGING.md).
        "R2_ACCESS_KEY_ID": "staging-token-id",
        "R2_SECRET_ACCESS_KEY": "staging-token-secret",
        # The VAPID pair: two Secret Manager slots (T-9.4, D-856).
        **vapid_settings(),
        **gce_env("staging"),
    }

    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]

    assert (settings.ENV, settings.COOKIE_DOMAIN) == (
        "staging",
        "staging.veloraapp.co.in",
    )


def test_staging_and_production_both_accept_velora_ic_tokens() -> None:
    """One Firebase project for both (D-065), never a test number in it. P-66
    gives staging a project of its own: when it does, staging's line changes and
    this test with it, so production refuses staging's tokens as an audience."""
    assert gce_env("staging")["FIREBASE_PROJECT_ID"] == "velora-ic"
    assert gce_env("production")["FIREBASE_PROJECT_ID"] == "velora-ic"


def test_productions_env_block_passes_settings() -> None:
    """The same for production's file: what CI's "Starts as production" step
    runs, here too, so a refusal shows before the image is built."""
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app:x@db.example:5432/postgres",
        "REDIS_URL": "rediss://default:x@redis.example:6379/0",
        **random_keys(),
        # R2's token: in Secret Manager (infra/PRODUCTION.md).
        "R2_ACCESS_KEY_ID": "production-token-id",
        "R2_SECRET_ACCESS_KEY": "production-token-secret",
        # The VAPID pair: two Secret Manager slots (T-9.4, D-856).
        **vapid_settings(),
        **gce_env("production"),
    }

    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]

    assert settings.ENV == "production"


# --- Storage: everything s3 needs, R2's own endpoint outside local (T-4.1) ------

# A name nobody has listed anywhere, in any allowlist or test: a blacklist that
# names today's environments waves it through; an allowlist refuses it (rule 16).
UNNAMED_ENV = "env-nobody-has-named-2031"
_LOCAL_S3 = {
    "STORAGE_PROVIDER": "s3",
    "R2_ENDPOINT_URL": "http://127.0.0.1:9000",
    "R2_ACCESS_KEY_ID": "velora-local",
    "R2_SECRET_ACCESS_KEY": "velora-local-secret",
    "PUBLIC_CDN_URL": "http://127.0.0.1:9000/velora-public",
}


def test_staging_and_production_each_name_their_own_buckets_and_cdn() -> None:
    production = gce_env("production")
    staging = gce_env("staging")

    assert (staging["R2_BUCKET_PUBLIC"], staging["R2_BUCKET_PRIVATE"]) == (
        "velora-staging-public",
        "velora-staging-private",
    )
    assert (production["R2_BUCKET_PUBLIC"], production["R2_BUCKET_PRIVATE"]) == (
        "velora-prod-public",
        "velora-prod-private",
    )
    assert staging["PUBLIC_CDN_URL"] == "https://cdn.staging.veloraapp.co.in"
    assert production["PUBLIC_CDN_URL"] == "https://cdn.veloraapp.co.in"
    # One account; R2's own endpoint, never an override.
    assert staging["R2_ACCOUNT_ID"] == production["R2_ACCOUNT_ID"]
    assert "R2_ENDPOINT_URL" not in staging
    assert "R2_ENDPOINT_URL" not in production


@pytest.mark.parametrize(
    "missing",
    [
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_PUBLIC",
        "R2_BUCKET_PRIVATE",
        "PUBLIC_CDN_URL",
    ],
)
@pytest.mark.parametrize("env", ["staging", "production"])
def test_s3_storage_missing_a_setting_refuses_to_start(env: str, missing: str) -> None:
    message = _error(ENV=env, **{**_DEPLOYED, missing: ""})

    assert f"STORAGE_PROVIDER=s3 needs {missing}" in message


def test_every_missing_storage_setting_is_named_at_once() -> None:
    blank = {
        name: ""
        for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    }
    message = _error(ENV="staging", **{**_DEPLOYED, **blank})

    assert "needs R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (" in message


def test_locally_the_local_s3_needs_no_account() -> None:
    settings = _settings(ENV="local", **_LOCAL_S3)

    assert (settings.R2_ACCOUNT_ID, settings.R2_ENDPOINT_URL) == (
        "",
        "http://127.0.0.1:9000",
    )


def test_fake_storage_needs_nothing() -> None:
    assert _settings(ENV="local").STORAGE_PROVIDER == "fake"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_an_endpoint_override_outside_local_refuses_to_start(env: str) -> None:
    message = _error(
        ENV=env, **{**_DEPLOYED, "R2_ENDPOINT_URL": "https://s3.elsewhere.example"}
    )

    assert f"ENV={env} cannot set R2_ENDPOINT_URL" in message
    assert "s3.elsewhere.example" not in message


@pytest.mark.parametrize("env", ["staging", "production", "preview", UNNAMED_ENV])
def test_the_endpoint_gate_is_an_allowlist(env: str) -> None:
    """Called on settings copied past validation, so even a name nobody has
    listed reaches the check: refused, as a blacklist would not."""
    settings = _settings(ENV="local", **_LOCAL_S3).model_copy(update={"ENV": env})

    with pytest.raises(ValueError, match=f"ENV={env} cannot set R2_ENDPOINT_URL"):
        # pydantic's decorator hides that it's a method; it is one.
        settings._storage_endpoint_only_where_allowed()  # type: ignore[operator]


@pytest.mark.parametrize("env", ["staging", "production", "preview", UNNAMED_ENV])
def test_a_plain_http_cdn_is_refused_outside_local(env: str) -> None:
    settings = _settings(ENV="production", **_DEPLOYED).model_copy(
        update={"ENV": env, "PUBLIC_CDN_URL": "http://cdn.example.test"}
    )

    with pytest.raises(
        ValueError, match=f"ENV={env} needs PUBLIC_CDN_URL to start with https://"
    ):
        # pydantic's decorator hides that it's a method; it is one.
        settings._s3_storage_is_complete()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("R2_ACCOUNT_ID", "82F9B26266DDB6B491A623971F87D3C7", "32 lowercase hex"),
        ("R2_ACCOUNT_ID", '82f9b26266ddb6b491a623971f87d3c7"', "32 lowercase hex"),
        ("PUBLIC_CDN_URL", "https://cdn.example.test/", "not end with /"),
        ("PUBLIC_CDN_URL", "cdn.example.test", "start with https://"),
        ("R2_BUCKET_PRIVATE", "velora-test-public", "must differ"),
    ],
)
def test_a_badly_shaped_storage_setting_is_named_but_not_echoed(
    name: str, value: str, expected: str
) -> None:
    message = _error(ENV="staging", **{**_DEPLOYED, name: value})

    assert expected in message
    if name == "R2_ACCOUNT_ID":
        assert value not in message


# --- GST (D-450, D-482) --------------------------------------------------------------


def test_velora_is_unregistered_for_gst_by_default() -> None:
    assert _settings().GST_REGISTERED is False
    assert _settings(GST_REGISTERED="false").GST_REGISTERED is False


@pytest.mark.parametrize("registered", ["true", "1", "yes"])
def test_registering_for_gst_refuses_to_start_until_p350_builds_it(
    registered: str,
) -> None:
    """The flag alone would change nothing and look as if it had: the split,
    the receipt's GST line, rate and GSTIN are P-350's task."""
    with pytest.raises(ValidationError) as excinfo:
        _settings(GST_REGISTERED=registered)

    message = str(excinfo.value)
    assert "GST_REGISTERED=true needs P-350's task first" in message
    assert "D-482" in message
