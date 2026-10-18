"""Whose limit a request counts against (core/deps.py, D-056)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.core.deps import UNKNOWN_CLIENT, bucket_for, client_bucket, client_ipv6_48
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


# Local settings shaped like the VMs': the address comes from the proxy's header.
_CADDY = _settings(CLIENT_IP_HEADER="Caddy-Client-IP")
_FORGED = {"X-Forwarded-For": "198.51.100.9, 10.1.2.3"}


def test_behind_caddy_the_proxy_header_decides_not_the_socket_or_forwarded_for() -> (
    None
):
    request = _request(_CADDY, {"Caddy-Client-IP": "203.0.113.7", **_FORGED})

    assert client_bucket(request) == "203.0.113.7"


def test_behind_caddy_a_request_without_the_header_shares_one_bucket() -> None:
    """Leaving the header out, or forging X-Forwarded-For, escapes nothing."""
    assert client_bucket(_request(_CADDY)) == UNKNOWN_CLIENT
    assert client_bucket(_request(_CADDY, _FORGED)) == UNKNOWN_CLIENT


def test_behind_caddy_a_garbled_header_shares_one_bucket() -> None:
    request = _request(_CADDY, {"Caddy-Client-IP": "198.51.100.9, 203.0.113.7"})

    assert client_bucket(request) == UNKNOWN_CLIENT


# Both proxies' headers are allowed while Fly and the VMs both run (D-1021), but
# each deployment reads only the one its CLIENT_IP_HEADER names: a client behind
# Caddy can't pick its bucket by sending Fly's header, nor the reverse.
_BOTH = [("Caddy-Client-IP", "Fly-Client-IP"), ("Fly-Client-IP", "Caddy-Client-IP")]


@pytest.mark.parametrize(("configured", "other"), _BOTH)
def test_a_deployment_reads_only_the_header_it_names(
    configured: str, other: str
) -> None:
    staging = _settings(CLIENT_IP_HEADER=configured).model_copy(
        update={"ENV": "staging"}
    )
    request = _request(
        staging,
        {configured: "203.0.113.7", other: "198.51.100.1", **_FORGED},
    )

    assert client_bucket(request) == "203.0.113.7"


@pytest.mark.parametrize(("configured", "other"), _BOTH)
def test_the_other_proxys_header_alone_escapes_nothing(
    configured: str, other: str
) -> None:
    """Forged on its own, the other proxy's header (and X-Forwarded-For) lands
    in the shared bucket, as a request with no header at all does."""
    staging = _settings(CLIENT_IP_HEADER=configured).model_copy(
        update={"ENV": "staging"}
    )
    for i in range(3):
        request = _request(staging, {other: f"198.51.100.{i + 1}", **_FORGED})
        assert client_bucket(request) == UNKNOWN_CLIENT
        assert client_ipv6_48(_request(staging, {other: f"2001:db8:{i}::1"})) is None


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


# --- The IPv6 /48 a request came from (D-066) ---------------------------------


@pytest.mark.parametrize(
    ("raw", "network"),
    [
        ("2001:db8:abcd:12::1", "2001:db8:abcd::/48"),
        ("2001:db8:abcd:ffff:ffff:ffff:ffff:ffff", "2001:db8:abcd::/48"),
        ("2001:db8:abce::1", "2001:db8:abce::/48"),
        (" 2001:db8:abcd:12::1 ", "2001:db8:abcd::/48"),
        ("203.0.113.7", None),  # IPv4 has no /48: its limit is the address's
        ("::ffff:203.0.113.7", None),  # nor does IPv4 written as IPv6
        ("not-an-address", None),
        (None, None),
    ],
)
def test_client_ipv6_48(raw: str | None, network: str | None) -> None:
    headers = {} if raw is None else {"Caddy-Client-IP": raw}

    assert client_ipv6_48(_request(_CADDY, headers)) == network


def test_the_48_comes_from_the_proxy_header_never_forwarded_for() -> None:
    request = _request(
        _CADDY,
        {"Caddy-Client-IP": "2001:db8:abcd::1", "X-Forwarded-For": "2001:db8:9::1"},
    )

    assert client_ipv6_48(request) == "2001:db8:abcd::/48"
