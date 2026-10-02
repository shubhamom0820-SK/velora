"""Application settings.

Every environment variable the API reads is declared here and nowhere else
(`02-ARCHITECTURE.md` §11). Required variables have no default, so a missing one
raises at import time rather than at the first request that needs it.

Secrets live only in the environment (CLAUDE.md rule 13). `.env` is read for
local development and is git-ignored; `.env.example` documents every name.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from redis.asyncio.connection import parse_url as parse_redis_url
from sqlalchemy.engine import make_url

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
    JWT_SECRET: str
    PHONE_PEPPER: str
    PHONE_ENC_KEY: str

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
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""

    # --- SMS (Path B) ---
    SMS_PROVIDER: SmsProvider = "fake"
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
