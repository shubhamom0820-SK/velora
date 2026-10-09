"""Web Push notifications (T-9.4).

`WebPush` encrypts each message for the browser that subscribed (RFC 8291:
aes128gcm, RFC 8188, one record), signs a VAPID token for the push service
(RFC 8292, ES256), and POSTs it with httpx. No library beyond the stack's own:
`cryptography` for the keys and the cipher, PyJWT for the token.

The push service (Google's, Mozilla's, Apple's, Microsoft's) sees the
endpoint, the size and the time, never the content: only the browser holds
the key that opens it (D-857). The endpoint, `p256dh` and `auth` are secrets
of the subscription, never logged (rule 15); httpx's own request line, which
names the endpoint, is dropped for push hosts (`_HideEndpoints`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, Protocol

import httpx
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core import clock
from app.core.vapid import (
    b64url_decode,
    public_bytes,
    vapid_private_key,
    vapid_public_key,
    vapid_token,
)


@dataclass(frozen=True)
class PushSubscription:
    endpoint: str
    p256dh: str
    auth: str


# "gone": the browser dropped the subscription (HTTP 404/410), so delete it.
# "retry": the push service failed or didn't answer; try again later.
PushOutcome = Literal["sent", "gone", "retry"]
Urgency = Literal["normal", "high"]


class PushProvider(Protocol):
    async def send(
        self,
        subscription: PushSubscription,
        payload: Mapping[str, object],
        *,
        ttl_s: int,
        urgency: Urgency = "normal",
    ) -> PushOutcome: ...

    async def aclose(self) -> None: ...


class FakePush:
    """Records every notification. Endpoints in `gone_endpoints` answer "gone",
    those in `failing_endpoints` "retry"."""

    def __init__(self) -> None:
        self.sent: list[tuple[PushSubscription, dict[str, object]]] = []
        self.gone_endpoints: set[str] = set()
        self.failing_endpoints: set[str] = set()

    async def send(
        self,
        subscription: PushSubscription,
        payload: Mapping[str, object],
        *,
        ttl_s: int,
        urgency: Urgency = "normal",
    ) -> PushOutcome:
        if subscription.endpoint in self.gone_endpoints:
            return "gone"
        if subscription.endpoint in self.failing_endpoints:
            return "retry"
        self.sent.append((subscription, dict(payload)))
        return "sent"

    async def aclose(self) -> None:
        pass


class NoPush:
    """`PUSH_PROVIDER=off` (D-856, amended): push is off, everywhere it is set.
    `GET /push/key` is then 404, so no browser subscribes and nothing waits in
    the outbox. A subscription made under another setting can't be pushed
    with no key: it answers "gone", and the sender deletes it."""

    async def send(
        self,
        subscription: PushSubscription,
        payload: Mapping[str, object],
        *,
        ttl_s: int,
        urgency: Urgency = "normal",
    ) -> PushOutcome:
        return "gone"

    async def aclose(self) -> None:
        pass


# --- RFC 8291 ----------------------------------------------------------------------

RECORD_SIZE: Final = 4096
_KEY_INFO: Final = b"WebPush: info\x00"
_CEK_INFO: Final = b"Content-Encoding: aes128gcm\x00"
_NONCE_INFO: Final = b"Content-Encoding: nonce\x00"
# One record holds the message, the 0x02 delimiter and GCM's 16-byte tag.
MAX_PLAINTEXT: Final = RECORD_SIZE - 86 - 1 - 16


def _hkdf_one_block(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA-256 (RFC 5869) for an output of one block or less."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:length]


def encrypt(
    plaintext: bytes,
    ua_public: bytes,
    auth_secret: bytes,
    *,
    as_private: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    """The aes128gcm body for one browser: header, then one record. A fresh
    key and salt per message unless a test gives them (RFC 8291 §3.4)."""
    if len(plaintext) > MAX_PLAINTEXT:
        raise ValueError("a push message is at most one record")
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    as_public = public_bytes(as_private.public_key())
    ecdh_secret = as_private.exchange(ec.ECDH(), receiver)
    ikm = _hkdf_one_block(
        auth_secret, ecdh_secret, _KEY_INFO + ua_public + as_public, 32
    )
    cek = _hkdf_one_block(salt, ikm, _CEK_INFO, 16)
    nonce = _hkdf_one_block(salt, ikm, _NONCE_INFO, 12)
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public
    return header + ciphertext


# --- The real one --------------------------------------------------------------------

TIMEOUT_S: Final = 10.0
_GONE: Final = frozenset({404, 410})


class _HideEndpoints(logging.Filter):
    """httpx logs each request's URL at INFO; a push's names its endpoint."""

    def __init__(self, hosts: tuple[str, ...]) -> None:
        super().__init__()
        self._hosts = hosts

    def filter(self, record: logging.LogRecord) -> bool:
        return not any(host in str(record.args) for host in self._hosts)


_FILTER: Final = _HideEndpoints(
    (
        "push.apple.com",
        "fcm.googleapis.com",
        "push.services.mozilla.com",
        "notify.windows.com",
    )
)


class WebPush:
    """VAPID Web Push over httpx. The client opens on first use, so the API,
    which builds every provider and never pushes, opens none."""

    def __init__(
        self,
        private_key: str,
        subject: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._private = vapid_private_key(private_key)
        self._public = vapid_public_key(self._private)
        self._subject = subject
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        logging.getLogger("httpx").addFilter(_FILTER)

    async def send(
        self,
        subscription: PushSubscription,
        payload: Mapping[str, object],
        *,
        ttl_s: int,
        urgency: Urgency = "normal",
    ) -> PushOutcome:
        body = encrypt(
            json.dumps(dict(payload), separators=(",", ":")).encode(),
            b64url_decode(subscription.p256dh),
            b64url_decode(subscription.auth),
        )
        token = vapid_token(
            self._private, subscription.endpoint, self._subject, clock.now()
        )
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=TIMEOUT_S, transport=self._transport
            )
        try:
            response = await self._client.post(
                subscription.endpoint,
                content=body,
                headers={
                    "Authorization": f"vapid t={token}, k={self._public}",
                    "Content-Encoding": "aes128gcm",
                    "Content-Type": "application/octet-stream",
                    "TTL": str(ttl_s),
                    "Urgency": urgency,
                },
            )
        except httpx.HTTPError:
            return "retry"
        if response.status_code in _GONE:
            return "gone"
        if 200 <= response.status_code < 300:
            return "sent"
        return "retry"

    async def aclose(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()
