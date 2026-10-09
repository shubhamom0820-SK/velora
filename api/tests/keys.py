"""Keys for tests that build `Settings` by hand and don't care which keys,
R2's included, which `STORAGE_PROVIDER=s3` needs (T-4.1).

Fresh and random on every call, shaped as `Settings` requires (D-060). Being
written nowhere, they pass in every environment, unlike the repo's public test
keys (`config.PUBLIC_TEST_KEYS`), which staging and production refuse.
"""

from __future__ import annotations

import secrets

from app.core.vapid import new_pair


def random_keys() -> dict[str, str]:
    """Four fresh keys: one of each the API requires."""
    return {
        "JWT_SECRET": secrets.token_hex(64),
        "PHONE_PEPPER": secrets.token_hex(32),
        "PHONE_ENC_KEY": secrets.token_hex(32),
        "CODE_PEPPER": secrets.token_hex(32),
    }


def r2_settings() -> dict[str, str]:
    """Everything `STORAGE_PROVIDER=s3` needs outside local, shaped as `Settings`
    requires and pointing nowhere real."""
    return {
        "R2_ACCOUNT_ID": secrets.token_hex(16),
        "R2_ACCESS_KEY_ID": secrets.token_hex(16),
        "R2_SECRET_ACCESS_KEY": secrets.token_hex(32),
        "R2_BUCKET_PUBLIC": "velora-test-public",
        "R2_BUCKET_PRIVATE": "velora-test-private",
        "PUBLIC_CDN_URL": "https://cdn.example.test",
    }


def vapid_settings() -> dict[str, str]:
    """Everything `PUSH_PROVIDER=webpush` needs (T-9.4): a fresh VAPID pair and
    a subject, pointing nowhere real."""
    return {**new_pair(), "VAPID_SUBJECT": "mailto:push@example.test"}
