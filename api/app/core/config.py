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

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Env = Literal["local", "staging", "production"]
PhoneProvider = Literal["firebase", "msg91", "fake"]
SmsProvider = Literal["msg91", "fake"]
PaymentsProvider = Literal["razorpay", "fake"]
ModerationProvider = Literal["sightengine", "fake"]
FaceMatchProvider = Literal["rekognition", "fake"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Core: required, no defaults. Missing one fails startup. ---
    ENV: Env
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str
    PHONE_PEPPER: str
    PHONE_ENC_KEY: str

    # --- Web origins and cookies ---
    # NoDecode: pydantic-settings would otherwise try to JSON-parse this
    # before the validator below sees the comma-separated string.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=list)
    COOKIE_DOMAIN: str = ""

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
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_PUBLIC: str = "velora-public"
    R2_BUCKET_PRIVATE: str = "velora-private"
    R2_ENDPOINT_URL: str = ""
    PUBLIC_CDN_URL: str = ""

    # --- Web push ---
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = ""

    # --- Observability. The SDK itself arrives in T-9.12. ---
    SENTRY_DSN: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """`CORS_ORIGINS` is a comma-separated list of exact origins (§12)."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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
