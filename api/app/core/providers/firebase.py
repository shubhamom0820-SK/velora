"""Google's public keys for Firebase ID tokens: Path A, the launch sign-in
(D-035, D-085).

The browser signs in with Firebase and hands us its ID token. Checking it takes
the project ID and Google's public keys, and nothing else: no service account.
This provider fetches the keys the way Google's "verify ID tokens using a
third-party JWT library" says to: the X.509 certificates at `CERTS_URL`, kept
for the `max-age` in that response's Cache-Control. Over httpx, never a
blocking client (rule 7), and timed by `core.clock`, so tests move it.

What a token must say is policy, in `core.security.verify_firebase_id_token`.
"""

from __future__ import annotations

import asyncio
import functools
import json
import re
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import clock

CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
FETCH_TIMEOUT_S = 5.0
# Google sends a max-age (about six hours when read on 4 October 2026); if a
# response ever lacks one, the keys are kept this long.
DEFAULT_MAX_AGE = timedelta(hours=1)
# A token naming a key we don't hold makes us fetch again, in case Google has
# just rotated, but no more often than this: tokens with made-up key IDs must not
# turn into a stream of requests to Google.
REFETCH_AT_MOST_EVERY = timedelta(minutes=1)
_MAX_AGE = re.compile(r"(?:^|,)\s*max-age\s*=\s*(\d+)\s*(?:,|$)", re.IGNORECASE)


class FirebaseKeysUnavailable(Exception):
    """Google's keys couldn't be read: a network failure, an error status, or a
    body that isn't the certificates. Not the token's fault, so the caller
    answers 503, never "invalid token"."""


class FirebaseKeys(Protocol):
    async def key_for(self, kid: str) -> rsa.RSAPublicKey | None:
        """The key Google signs ID tokens with under `kid`, or None when Google
        lists no such key. Raises `FirebaseKeysUnavailable` when it can't tell."""
        ...


class GoogleFirebaseKeys:
    """The real keys, from `CERTS_URL`. One instance per app; nothing is fetched
    until the first token arrives."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # Tests pass an httpx.MockTransport; nothing in a test reaches Google.
        self._transport = transport
        self._keys: dict[str, rsa.RSAPublicKey] = {}
        self._fresh_until: datetime | None = None
        self._fetched_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def key_for(self, kid: str) -> rsa.RSAPublicKey | None:
        if self._needs_fetch(kid):
            async with self._lock:
                # Another request may have fetched while this one waited.
                if self._needs_fetch(kid):
                    await self._fetch()
        return self._keys.get(kid)

    def _needs_fetch(self, kid: str) -> bool:
        now = clock.now()
        if self._fresh_until is None or now >= self._fresh_until:
            return True
        if kid in self._keys:
            return False
        return (
            self._fetched_at is None or now - self._fetched_at >= REFETCH_AT_MOST_EVERY
        )

    async def _fetch(self) -> None:
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=FETCH_TIMEOUT_S
            ) as client:
                response = await client.get(CERTS_URL)
        except httpx.HTTPError:
            raise FirebaseKeysUnavailable(
                "Google's keys couldn't be fetched."
            ) from None
        if response.status_code != 200:
            raise FirebaseKeysUnavailable(
                f"Google's keys answered {response.status_code}."
            )
        keys = _parse_certificates(response.content)
        now = clock.now()
        self._keys = keys
        self._fetched_at = now
        self._fresh_until = now + _max_age(response.headers.get("cache-control"))


def _parse_certificates(body: bytes) -> dict[str, rsa.RSAPublicKey]:
    """`{kid: PEM certificate}`, each holding an RSA key, or nothing at all: a
    body that is partly wrong replaces no keys."""
    unreadable = FirebaseKeysUnavailable("Google's keys couldn't be read.")
    try:
        listed: Any = json.loads(body)
    except ValueError:
        raise unreadable from None
    if not isinstance(listed, dict) or not listed:
        raise unreadable
    keys: dict[str, rsa.RSAPublicKey] = {}
    for kid, pem in listed.items():
        if not isinstance(kid, str) or not isinstance(pem, str):
            raise unreadable
        try:
            key = x509.load_pem_x509_certificate(pem.encode()).public_key()
        except ValueError:
            raise unreadable from None
        if not isinstance(key, rsa.RSAPublicKey):
            raise unreadable
        keys[kid] = key
    return keys


def _max_age(cache_control: str | None) -> timedelta:
    match = _MAX_AGE.search(cache_control or "")
    return timedelta(seconds=int(match.group(1))) if match else DEFAULT_MAX_AGE


@functools.cache
def _fake_signing_key() -> rsa.RSAPrivateKey:
    # Generated once per test run: 2048-bit keys take tens of milliseconds, and
    # every test builds a FakeProviders.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeFirebaseKeys:
    """Google's part, for tests: a key pair of its own, published under `KID`,
    and `sign()` to mint tokens with it.

    Only `FakeProviders` builds it; `build_providers` never does, so no running
    app trusts a key Google didn't publish. Set `unavailable` to make every
    lookup fail as an outage would.
    """

    KID = "fake-firebase-kid"

    def __init__(self) -> None:
        self.unavailable = False
        self.lookups = 0

    async def key_for(self, kid: str) -> rsa.RSAPublicKey | None:
        self.lookups += 1
        if self.unavailable:
            raise FirebaseKeysUnavailable("Google's keys couldn't be fetched.")
        return _fake_signing_key().public_key() if kid == self.KID else None

    def sign(
        self,
        claims: dict[str, Any],
        *,
        kid: str = KID,
        key: rsa.RSAPrivateKey | None = None,
    ) -> str:
        """An RS256 token over `claims`, signed with this fake's key or `key`."""
        return jwt.encode(
            claims,
            key or _fake_signing_key(),
            algorithm="RS256",
            headers={"kid": kid},
        )
