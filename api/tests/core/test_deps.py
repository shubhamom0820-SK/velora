"""Whose limit a request counts against (core/deps.py, D-056)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.core.deps import UNKNOWN_CLIENT, bucket_for, client_bucket
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL
from tests.keys import random_keys


def _request(
    settings: Settings,
    headers: dict[str, str] | None = None,
    socket: str | None = "10.1.2.3",
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/waitlist",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (socket, 50000) if socket else None,
        "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
    }
    return Request(scope)


_REQUIRED = {
    "ENV": "local",
    "DATABASE_URL": TEST_DATABASE_URL,
    "REDIS_URL": TEST_REDIS_URL,
    **random_keys(),
}


def _settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **overrides})  # type: ignore[arg-type]


# Local settings shaped like Fly's: the address comes from the proxy's header.
_FLY = _settings(CLIENT_IP_HEADER="Fly-Client-IP")
_FORGED = {"X-Forwarded-For": "198.51.100.9, 10.1.2.3"}


def test_on_fly_the_proxy_header_decides_not_the_socket_or_forwarded_for() -> None:
    request = _request(_FLY, {"Fly-Client-IP": "203.0.113.7", **_FORGED})

    assert client_bucket(request) == "203.0.113.7"


def test_on_fly_a_request_without_the_header_shares_one_bucket() -> None:
    """Leaving the header out, or forging X-Forwarded-For, escapes nothing."""
    assert client_bucket(_request(_FLY)) == UNKNOWN_CLIENT
    assert client_bucket(_request(_FLY, _FORGED)) == UNKNOWN_CLIENT


def test_on_fly_a_garbled_header_shares_one_bucket() -> None:
    request = _request(_FLY, {"Fly-Client-IP": "198.51.100.9, 203.0.113.7"})

    assert client_bucket(request) == UNKNOWN_CLIENT


def test_locally_without_a_header_the_socket_decides() -> None:
    request = _request(_settings(), _FORGED, socket="127.0.0.1")

    assert client_bucket(request) == "127.0.0.1"


def test_outside_local_the_socket_is_never_read() -> None:
    """Belt and braces: settings refuse to start like this (test_config), and
    if they somehow did, the request lands in the shared bucket, not the proxy's."""
    staging = _settings().model_copy(update={"ENV": "staging"})

    assert client_bucket(_request(staging, socket="10.1.2.3")) == UNKNOWN_CLIENT


@pytest.mark.parametrize(
    ("raw", "bucket"),
    [
        ("203.0.113.7", "203.0.113.7"),
        (" 203.0.113.7 ", "203.0.113.7"),
        # One home connection gets a whole /64: the limit is on the /64.
        ("2001:db8:1:2::1", "2001:db8:1:2::/64"),
        ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
        ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
        # IPv4 written as IPv6 is still that IPv4 address.
        ("::ffff:203.0.113.7", "203.0.113.7"),
        (None, UNKNOWN_CLIENT),
        ("", UNKNOWN_CLIENT),
        ("not-an-ip", UNKNOWN_CLIENT),
        ("203.0.113.7:443", UNKNOWN_CLIENT),
    ],
)
def test_bucket_for(raw: str | None, bucket: str) -> None:
    assert bucket_for(raw) == bucket
