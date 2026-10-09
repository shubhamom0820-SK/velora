"""VAPID keys and tokens (RFC 8292, T-9.4), with no I/O: the push provider
signs with them, and settings check the pair at startup (D-856).

A key pair is P-256: the private key's 32-byte scalar and the public key's
65-byte uncompressed point, each base64url without padding, the form browsers
take as `applicationServerKey`.
"""

from __future__ import annotations

import base64
import sys
from datetime import datetime, timedelta
from typing import Final
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)


# A push service refuses a token valid for more than 24 hours.
VAPID_LIFETIME: Final = timedelta(hours=12)


def vapid_private_key(raw: str) -> ec.EllipticCurvePrivateKey:
    """The VAPID private key from its base64url 32 bytes."""
    scalar = b64url_decode(raw)
    if len(scalar) != 32:
        raise ValueError("a VAPID private key is 32 bytes, base64url")
    return ec.derive_private_key(int.from_bytes(scalar, "big"), ec.SECP256R1())


def vapid_public_key(private: ec.EllipticCurvePrivateKey) -> str:
    return b64url_encode(public_bytes(private.public_key()))


def vapid_token(
    private: ec.EllipticCurvePrivateKey, endpoint: str, subject: str, now: datetime
) -> str:
    parts = urlsplit(endpoint)
    claims = {
        "aud": f"{parts.scheme}://{parts.netloc}",
        "exp": int((now + VAPID_LIFETIME).timestamp()),
        "sub": subject,
    }
    return jwt.encode(claims, private, algorithm="ES256", headers={"typ": "JWT"})


def new_pair() -> dict[str, str]:
    """A fresh key pair, as the two settings hold it."""
    private = ec.generate_private_key(ec.SECP256R1())
    raw = private.private_numbers().private_value.to_bytes(32, "big")
    return {
        "VAPID_PRIVATE_KEY": b64url_encode(raw),
        "VAPID_PUBLIC_KEY": vapid_public_key(private),
    }


def main() -> int:
    """`python -m app.core.vapid`: a fresh pair as `NAME=value` lines, for a
    pipe only, never a screen (D-856). Into Fly, unseen:
    `python -m app.core.vapid | fly secrets import -a <app>`; CI pipes a
    throwaway pair into `$GITHUB_ENV`."""
    if sys.stdout.isatty():
        sys.stderr.write(
            "Refused: this prints a private key. Pipe it into `fly secrets import` "
            "(infra/STAGING.md), never to a screen.\n"
        )
        return 2
    sys.stdout.write("".join(f"{name}={value}\n" for name, value in new_pair().items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
