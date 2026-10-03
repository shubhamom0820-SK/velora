"""Application settings.

Every environment variable the API reads is declared here and nowhere else
(`02-ARCHITECTURE.md` §11). Required variables have no default, so a missing one
raises at import time rather than at the first request that needs it.

Secrets live only in the environment (CLAUDE.md rule 13). `.env` is read for
local development and is git-ignored; `.env.example` documents every name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from redis.asyncio.connection import parse_url as parse_redis_url
from sqlalchemy.engine import make_url

# The brand: one constant, so a rename stays cheap (D-015). Thread and Knot are
# product nouns and never read it (rule 17). The web's twin is web/src/lib/app.ts.
APP_NAME = "Velora"

Env = Literal["local", "staging", "production"]
PhoneProvider = Literal["firebase", "msg91", "fake"]
SmsProvider = Literal["msg91", "fake"]
PaymentsProvider = Literal["razorpay", "fake"]
ModerationProvider = Literal["sightengine", "fake"]
FaceMatchProvider = Literal["rekognition", "fake"]
StorageProvider = Literal["s3", "fake"]
PushProvider = Literal["webpush", "fake"]

# Where fake providers may run: an allowlist (CLAUDE.md rule 16, D-045). A fake
# payments gateway grants free credits and a fake sign-in lets anyone in as
# anyone, so every other environment must name a real provider for each of these.
FAKES_ALLOWED_IN: frozenset[str] = frozenset({"local"})
# Where Redis may be reached without TLS (`redis://`): an allowlist again.
# Everywhere else it's `rediss://` (Upstash requires it).
PLAIN_REDIS_ALLOWED_IN: frozenset[str] = frozenset({"local"})
# Where a client's IP may come from the socket: an allowlist (D-056). Behind
# Fly's proxy the socket is the proxy, and uvicorn's own client address trusts
# X-Forwarded-For, which the client writes; everywhere else the address comes
# from the header the platform sets, CLIENT_IP_HEADER.
SOCKET_CLIENT_IP_ALLOWED_IN: frozenset[str] = frozenset({"local"})
# The keys this repo publishes for the tests and CI: tests/conftest.py and
# .github/workflows/ci.yml use exactly these. Anyone who can read the repo can
# sign access tokens, test phone hashes and decrypt phone numbers with them, and
# nothing would fail, so they work only where ENV is local (rule 16, D-060).
# Hex of one repeated letter each, so a stray one is recognisable: j(wt),
# p(epper), e(ncryption), c(ode).
PUBLIC_TEST_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "JWT_SECRET": "6a" * 64,
        "PHONE_PEPPER": "70" * 32,
        "PHONE_ENC_KEY": "65" * 32,
        "CODE_PEPPER": "63" * 32,
    }
)
TEST_KEYS_ALLOWED_IN: frozenset[str] = frozenset({"local"})
# Where a real SMS provider may text any number: an allowlist (rule 16, D-064).
# India reserves no fictional range, so the seed's numbers may be real people's;
# everywhere else, local and any environment named later, a real provider is
# called only for the numbers in SMS_LOCAL_ALLOWED_TO, which is empty by default.
REAL_SMS_TO_ANYONE_IN: frozenset[str] = frozenset({"staging", "production"})
# Where SMS_LOCAL_ALLOWED_TO may be set: an allowlist again. Anywhere else it
# would look like protection it isn't (D-066).
SMS_LOCAL_ALLOWED_TO_ALLOWED_IN: frozenset[str] = frozenset({"local"})
_HEX = re.compile(r"[0-9a-fA-F]+")
# A Google Cloud project ID: 6 to 30 lowercase letters, digits and hyphens,
# starting with a letter and not ending with a hyphen.
_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
PROVIDER_SETTINGS = (
    "AUTH_PHONE_PROVIDER",
    "SMS_PROVIDER",
    "PAYMENTS_PROVIDER",
    "MODERATION_PROVIDER",
    "FACEMATCH_PROVIDER",
    "STORAGE_PROVIDER",
    "PUSH_PROVIDER",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        # A validation error names the setting but never echoes its value: one
        # day the bad value is a database URL, and the error lands in Fly's logs.
        hide_input_in_errors=True,
    )

    # --- Core: required, no defaults. Missing one fails startup. ---
    ENV: Env
    DATABASE_URL: str
    REDIS_URL: str
    # Keys: hex from `openssl rand -hex …`, checked below (D-060).
    JWT_SECRET: str
    # Never changes once a number is banned: a ban keeps only the hash (D-061).
    PHONE_PEPPER: str
    # One key, or several separated by commas, newest first: the first encrypts
    # and every one decrypts, so adding a key is a config change (D-061).
    PHONE_ENC_KEY: Annotated[tuple[str, ...], NoDecode]
    # The pepper for the short codes people type: PINs, and OTP codes from T-3.2
    # (D-062, D-063). Never PHONE_PEPPER's key: this one can rotate.
    CODE_PEPPER: str

    # --- Database pool, per process (each uvicorn worker opens its own) ---
    DB_POOL_SIZE: int = Field(default=5, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0)

    # --- Web origins and cookies ---
    # NoDecode: pydantic-settings would otherwise try to JSON-parse this
    # before the validator below sees the comma-separated string.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=list)
    COOKIE_DOMAIN: str = ""
    # The header the platform's proxy puts the client's IP in, for per-IP rate
    # limits: `Fly-Client-IP` on Fly. Empty only where ENV is local (D-056).
    CLIENT_IP_HEADER: str = ""

    # --- Auth provider selection (D-035) ---
    AUTH_PHONE_PROVIDER: PhoneProvider = "fake"
    # The project whose ID tokens sign in (Path A, D-085): a token's audience
    # must be it, and its issuer https://securetoken.google.com/ followed by it.
    # Required where AUTH_PHONE_PROVIDER is firebase. Not secret, and no service
    # account goes with it: verifying needs only this and Google's public keys.
    FIREBASE_PROJECT_ID: str = ""

    # --- SMS (Path B) ---
    SMS_PROVIDER: SmsProvider = "fake"
    # Locally, the only numbers a real SMS provider is called for: comma-
    # separated, each normalised at startup, empty by default (D-064, D-066).
    # Refused outside local. Holds normalize_phone's output, so the guard
    # compares like with like.
    SMS_LOCAL_ALLOWED_TO: Annotated[tuple[str, ...], NoDecode] = ()
    MSG91_AUTH_KEY: str = ""
    MSG91_TEMPLATE_ID: str = ""
    MSG91_SENDER_ID: str = ""

    # --- Payments ---
    PAYMENTS_PROVIDER: PaymentsProvider = "fake"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # --- Moderation (worker) ---
    MODERATION_PROVIDER: ModerationProvider = "fake"
    SIGHTENGINE_API_USER: str = ""
    SIGHTENGINE_API_SECRET: str = ""

    # --- Face match (worker) ---
    FACEMATCH_PROVIDER: FaceMatchProvider = "fake"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"

    # --- Object storage: R2 in deployed envs, MinIO locally (D-027) ---
    STORAGE_PROVIDER: StorageProvider = "fake"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_PUBLIC: str = "velora-public"
    R2_BUCKET_PRIVATE: str = "velora-private"
    R2_ENDPOINT_URL: str = ""
    PUBLIC_CDN_URL: str = ""

    # --- Web push ---
    PUSH_PROVIDER: PushProvider = "fake"
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = ""

    # --- Observability. The SDK itself arrives in T-9.12. ---
    SENTRY_DSN: str = ""

    # A malformed URL fails here, when the image checks settings before uvicorn
    # starts, instead of in every worker at startup — which crash-loops a
    # "running" machine. T-1.22 hit both: REDIS_URL holding a command, then a
    # stray closing quote. Each URL goes through the parser its client uses
    # (no connection is made), and the messages never include the value or
    # the parser's own error, either of which may carry a password.
    @field_validator("DATABASE_URL")
    @classmethod
    def _database_url_parses(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("must start with postgresql+asyncpg:// (the async driver)")
        try:
            make_url(v).port  # noqa: B018 — parsing the port is the check
        except Exception:  # noqa: BLE001 — any parse failure means the same thing
            raise ValueError(
                "isn't a valid database URL; check for stray quotes or spaces"
            ) from None
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def _redis_url_parses(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("must start with rediss:// (or redis:// locally)")
        try:
            parse_redis_url(v)
        except Exception:  # noqa: BLE001 — any parse failure means the same thing
            raise ValueError(
                "isn't a valid Redis URL; check for stray quotes or spaces"
            ) from None
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """`CORS_ORIGINS` is a comma-separated list of exact origins (§12)."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Keys are checked for shape, in every environment: a short or mistyped key
    # fails nothing later, it just protects less, so it fails here (D-060). Like
    # the URLs above, a message names what's wanted and never echoes the value.
    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_is_long_hex(cls, v: str) -> str:
        if not (_HEX.fullmatch(v) and len(v) >= 128 and len(v) % 2 == 0):
            raise ValueError(
                "must be at least 128 hex characters (64 bytes): generate it with "
                "`openssl rand -hex 64`; check for stray quotes or spaces"
            )
        return v

    @field_validator("PHONE_PEPPER", "CODE_PEPPER")
    @classmethod
    def _pepper_is_32_byte_hex(cls, v: str) -> str:
        if not (_HEX.fullmatch(v) and len(v) == 64):
            raise ValueError(
                "must be exactly 64 hex characters (32 bytes): generate it with "
                "`openssl rand -hex 32`; check for stray quotes or spaces"
            )
        return v

    @field_validator("PHONE_ENC_KEY", mode="before")
    @classmethod
    def _split_enc_keys(cls, v: object) -> object:
        """Comma-separated, newest first, nothing stripped: a stray space is an
        error to see, not something to tidy away."""
        if isinstance(v, str):
            return tuple(v.split(","))
        return v

    @field_validator("PHONE_ENC_KEY")
    @classmethod
    def _enc_keys_are_32_byte_hex(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v or not all(_HEX.fullmatch(key) and len(key) == 64 for key in v):
            raise ValueError(
                "must be one or more keys of exactly 64 hex characters (32 bytes), "
                "newest first, separated by commas with no spaces: generate one with "
                "`openssl rand -hex 32`"
            )
        if len({bytes.fromhex(key) for key in v}) != len(v):
            raise ValueError("lists the same key more than once")
        return v

    @field_validator("SMS_LOCAL_ALLOWED_TO", mode="before")
    @classmethod
    def _numbers_allowed_an_sms(cls, v: object) -> object:
        """Each number through `normalize_phone`, so `98765 43210` and
        `+919876543210` are the same entry. A number it refuses fails startup,
        named by its place in the list, never echoed (rule 15)."""
        if isinstance(v, str):
            entries: list[object] = list(v.split(","))
        elif isinstance(v, list | tuple):
            entries = list(v)
        else:
            return v
        # Imported here: security imports this module for Settings.
        from app.core.errors import AppError
        from app.core.security import normalize_phone

        numbers: list[str] = []
        for place, raw in enumerate(entries, start=1):
            if isinstance(raw, str) and not raw.strip():
                continue  # a trailing comma, or the empty default
            try:
                if not isinstance(raw, str):
                    raise TypeError
                numbers.append(normalize_phone(raw))
            except (AppError, TypeError):
                raise ValueError(
                    f"entry {place} isn't an Indian mobile number; list mobile "
                    "numbers separated by commas"
                ) from None
        return tuple(numbers)

    @model_validator(mode="after")
    def _sms_allowlist_only_where_allowed(self) -> Settings:
        """Refuse `SMS_LOCAL_ALLOWED_TO` outside where it means something.

        Elsewhere a real provider texts any number (`REAL_SMS_TO_ANYONE_IN`), so
        a list there would read as a guard that guards nothing (D-066).
        """
        if self.ENV in SMS_LOCAL_ALLOWED_TO_ALLOWED_IN or not self.SMS_LOCAL_ALLOWED_TO:
            return self
        raise ValueError(
            f"ENV={self.ENV} cannot set SMS_LOCAL_ALLOWED_TO: it limits who a real "
            "SMS provider texts only where ENV is "
            f"{', '.join(sorted(SMS_LOCAL_ALLOWED_TO_ALLOWED_IN))}, and here it would "
            "look like protection it isn't (D-066). Remove it."
        )

    @model_validator(mode="after")
    def _fakes_only_where_allowed(self) -> Settings:
        """Refuse to start with a fake provider outside `FAKES_ALLOWED_IN`.

        `ENV` itself has no default, so a deploy that forgets it fails above
        instead of quietly becoming "local" and passing this check.
        """
        if self.ENV in FAKES_ALLOWED_IN:
            return self
        fakes = [name for name in PROVIDER_SETTINGS if getattr(self, name) == "fake"]
        if fakes:
            raise ValueError(
                f"ENV={self.ENV} cannot use fake providers ({', '.join(fakes)}): fakes run "
                f"only where ENV is {', '.join(sorted(FAKES_ALLOWED_IN))} (D-045). "
                "Set a real provider for each."
            )
        return self

    @model_validator(mode="after")
    def _redis_uses_tls_where_required(self) -> Settings:
        """Plain `redis://` only where allowed; elsewhere `rediss://` (TLS)."""
        if self.ENV not in PLAIN_REDIS_ALLOWED_IN and not self.REDIS_URL.startswith(
            "rediss://"
        ):
            raise ValueError(
                f"ENV={self.ENV} needs REDIS_URL to use rediss:// (TLS); plain redis:// "
                f"is only for ENV {', '.join(sorted(PLAIN_REDIS_ALLOWED_IN))}."
            )
        return self

    @model_validator(mode="after")
    def _client_ip_header_where_required(self) -> Settings:
        """Outside `SOCKET_CLIENT_IP_ALLOWED_IN`, per-IP limits need the proxy's header.

        Without it the limiter would key on an address the client chooses, and
        every test would still pass: no test forges a header (D-056).
        """
        if self.ENV not in SOCKET_CLIENT_IP_ALLOWED_IN and not self.CLIENT_IP_HEADER:
            raise ValueError(
                f"ENV={self.ENV} needs CLIENT_IP_HEADER (Fly-Client-IP on Fly): the "
                "socket's address is the proxy's, and X-Forwarded-For is written by "
                "the client, so per-IP rate limits would key on an address anyone can "
                f"choose (D-056). Only ENV {', '.join(sorted(SOCKET_CLIENT_IP_ALLOWED_IN))} "
                "may read the socket."
            )
        return self

    @model_validator(mode="after")
    def _public_test_keys_only_where_allowed(self) -> Settings:
        """Refuse the repo's test keys outside `TEST_KEYS_ALLOWED_IN` (D-060).

        A copied test key fails nothing: tokens still verify and hashes still
        match, for us and for anyone who has read the repo. Compared as bytes, so
        a test key in capitals is still a test key.
        """
        if self.ENV in TEST_KEYS_ALLOWED_IN:
            return self
        in_use = {
            "JWT_SECRET": [self.JWT_SECRET],
            "PHONE_PEPPER": [self.PHONE_PEPPER],
            "PHONE_ENC_KEY": list(self.PHONE_ENC_KEY),
            "CODE_PEPPER": [self.CODE_PEPPER],
        }
        found = [
            name
            for name, test_key in PUBLIC_TEST_KEYS.items()
            if bytes.fromhex(test_key) in {bytes.fromhex(k) for k in in_use[name]}
        ]
        if found:
            raise ValueError(
                f"ENV={self.ENV} cannot use the repo's public test keys "
                f"({', '.join(found)}): anyone who can read the repo could sign access "
                "tokens and read phone numbers with them. They work only where ENV is "
                f"{', '.join(sorted(TEST_KEYS_ALLOWED_IN))} (D-060). Generate real ones "
                "with openssl rand -hex (infra/STAGING.md)."
            )
        return self

    @model_validator(mode="after")
    def _firebase_names_its_project(self) -> Settings:
        """Path A needs the project its tokens must come from (D-085).

        Without it every token would be refused for the wrong audience, and
        sign-in would fail at the first real try instead of at startup.
        """
        if self.AUTH_PHONE_PROVIDER != "firebase":
            return self
        if not self.FIREBASE_PROJECT_ID:
            raise ValueError(
                "AUTH_PHONE_PROVIDER=firebase needs FIREBASE_PROJECT_ID: the Firebase "
                "project whose ID tokens sign in (D-085)."
            )
        if not _PROJECT_ID.fullmatch(self.FIREBASE_PROJECT_ID):
            raise ValueError(
                "FIREBASE_PROJECT_ID must be a Firebase project ID: 6 to 30 lowercase "
                "letters, digits and hyphens, starting with a letter; check for stray "
                "quotes or spaces"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def debug(self) -> bool:
        return self.ENV == "local"


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is read and validated exactly once."""
    return Settings()
