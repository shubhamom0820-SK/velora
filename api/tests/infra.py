"""Skip, rather than fail, tests that need the real Postgres and Redis.

CI without Docker (T-1.20) must stay quiet, so tests that hit live infrastructure
carry `@requires_infra`. The check is a bare TCP connect, deliberately not the
app's own checks: a bug in `check_database()` must fail its test, not skip it.
"""

from __future__ import annotations

import socket
from urllib.parse import urlsplit

import pytest

from app.core.config import get_settings


def _reachable(url: str) -> bool:
    parts = urlsplit(url)
    if parts.hostname is None or parts.port is None:
        return False
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=0.5):
            return True
    except OSError:
        return False


_settings = get_settings()

requires_infra = pytest.mark.skipif(
    not (_reachable(_settings.DATABASE_URL) and _reachable(_settings.REDIS_URL)),
    reason="Postgres or Redis not reachable — start them with `make infra-up`",
)
