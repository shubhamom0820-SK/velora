"""Keys for tests that build `Settings` by hand and don't care which keys.

Fresh and random on every call, shaped as `Settings` requires (D-060). Being
written nowhere, they pass in every environment, unlike the repo's public test
keys (`config.PUBLIC_TEST_KEYS`), which staging and production refuse.
"""

from __future__ import annotations

import secrets


def random_keys() -> dict[str, str]:
    """Four fresh keys: one of each the API requires."""
    return {
        "JWT_SECRET": secrets.token_hex(64),
        "PHONE_PEPPER": secrets.token_hex(32),
        "PHONE_ENC_KEY": secrets.token_hex(32),
        "CODE_PEPPER": secrets.token_hex(32),
    }
