"""`WebPush` (T-9.4): RFC 8291's encryption, RFC 8292's token, and what the push
service's answer means. The encryption is held to RFC 8291's own example
(§5, Appendix A), byte for byte, read from the RFC's text on 9 October 2026;
and a message is opened again with the browser's key, as a browser would."""

from __future__ import annotations

import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.providers import build_providers
from app.core.providers.push import (
    NoPush,
    PushSubscription,
    WebPush,
    _hkdf_one_block,
    encrypt,
)
from app.core.vapid import (
    b64url_decode,
    b64url_encode,
    public_bytes,
    vapid_private_key,
    vapid_public_key,
    vapid_token,
)
from app.modules.notifications import service
from tests.conftest import make_test_settings
from tests.keys import r2_settings, random_keys
from tests.modules.notifications.support import browser_keys

# RFC 8291 §5 and Appendix A, whitespace removed.
PLAINTEXT = b"When I grow up, I want to be a watermelon"
AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
AUTH = "BTBZMqHH6r4Tts7J_aSIgg"  # gitleaks:allow (RFC 8291 §5's published example)
SALT = "DGv6ra1nlYgDCS1FRnbzlw"
BODY = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
    "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
    "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)

NOON = datetime(2026, 10, 9, 6, 30, tzinfo=UTC)
SUBJECT = "mailto:push@example.com"


def test_the_body_is_rfc_8291s_example_byte_for_byte() -> None:
    body = encrypt(
        PLAINTEXT,
        b64url_decode(UA_PUBLIC),
        b64url_decode(AUTH),
        as_private=vapid_private_key(AS_PRIVATE),
        salt=b64url_decode(SALT),
    )
    assert b64url_encode(body) == BODY


def _open(body: bytes, private: ec.EllipticCurvePrivateKey, auth: bytes) -> bytes:
    """What a browser does: read the header, derive the key, decrypt."""
    salt, as_public = body[:16], body[21:86]
    assert body[16:21] == (4096).to_bytes(4, "big") + bytes([65])
    sender = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    secret = private.exchange(ec.ECDH(), sender)
    ua_public = public_bytes(private.public_key())
    ikm = _hkdf_one_block(
        auth, secret, b"WebPush: info\x00" + ua_public + as_public, 32
    )
    cek = _hkdf_one_block(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf_one_block(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, body[86:], None)
    assert plain.endswith(b"\x02")
    return plain[:-1]


def test_a_browser_opens_what_was_sealed_for_it_and_no_other_can() -> None:
    private, keys = browser_keys()
    other, _ = browser_keys()
    body = encrypt(
        b'{"kind":"match"}', b64url_decode(keys["p256dh"]), b64url_decode(keys["auth"])
    )

    assert _open(body, private, b64url_decode(keys["auth"])) == b'{"kind":"match"}'
    with pytest.raises(Exception):  # noqa: B017 — any failure to open is the point
        _open(body, other, b64url_decode(keys["auth"]))


def test_each_message_has_its_own_key_and_salt() -> None:
    _, keys = browser_keys()
    first, second = (
        encrypt(b"x", b64url_decode(keys["p256dh"]), b64url_decode(keys["auth"]))
        for _ in range(2)
    )
    assert first[:86] != second[:86]


def test_a_message_over_one_record_is_refused() -> None:
    _, keys = browser_keys()
    with pytest.raises(ValueError, match="one record"):
        encrypt(b"x" * 4000, b64url_decode(keys["p256dh"]), b64url_decode(keys["auth"]))


def test_the_token_names_the_push_service_and_lasts_under_a_day() -> None:
    private = vapid_private_key(AS_PRIVATE)
    token = vapid_token(
        private, "https://fcm.googleapis.com/fcm/send/abc", SUBJECT, NOON
    )

    claims = jwt.decode(
        token,
        private.public_key(),
        algorithms=["ES256"],
        audience="https://fcm.googleapis.com",
        options={"verify_exp": False},
    )
    assert claims["sub"] == SUBJECT
    assert 0 < claims["exp"] - NOON.timestamp() <= 24 * 3600
    assert jwt.get_unverified_header(token) == {"typ": "JWT", "alg": "ES256"}


# --- Sending --------------------------------------------------------------------------


def _push(handler: httpx.MockTransport) -> WebPush:
    return WebPush(AS_PRIVATE, SUBJECT, transport=handler)


async def test_a_push_is_posted_sealed_with_its_headers() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201)

    private, keys = browser_keys()
    subscription = PushSubscription(
        "https://fcm.googleapis.com/fcm/send/abc", keys["p256dh"], keys["auth"]
    )
    push = _push(httpx.MockTransport(answer))

    outcome = await push.send(
        subscription, {"kind": "match"}, ttl_s=600, urgency="high"
    )
    await push.aclose()

    assert outcome == "sent"
    [request] = seen
    assert str(request.url) == subscription.endpoint
    assert request.headers["TTL"] == "600"
    assert request.headers["Urgency"] == "high"
    assert request.headers["Content-Encoding"] == "aes128gcm"
    scheme, _, rest = request.headers["Authorization"].partition(" ")
    token, key = (part.split("=", 1)[1] for part in rest.split(", "))
    assert (scheme, key) == ("vapid", vapid_public_key(vapid_private_key(AS_PRIVATE)))
    jwt.decode(
        token,
        vapid_private_key(AS_PRIVATE).public_key(),
        algorithms=["ES256"],
        audience="https://fcm.googleapis.com",
    )
    opened = _open(request.content, private, b64url_decode(keys["auth"]))
    assert json.loads(opened) == {"kind": "match"}


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (201, "sent"),
        (200, "sent"),
        (404, "gone"),
        (410, "gone"),
        (500, "retry"),
        (429, "retry"),
        (403, "retry"),
    ],
)
async def test_the_push_services_answer_decides(status: int, outcome: str) -> None:
    _, keys = browser_keys()
    push = _push(httpx.MockTransport(lambda _: httpx.Response(status)))
    subscription = PushSubscription(
        "https://fcm.googleapis.com/x", keys["p256dh"], keys["auth"]
    )
    assert await push.send(subscription, {}, ttl_s=60) == outcome
    await push.aclose()


async def test_no_answer_is_tried_again() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("no answer", request=request)

    _, keys = browser_keys()
    push = _push(httpx.MockTransport(down))
    subscription = PushSubscription(
        "https://fcm.googleapis.com/x", keys["p256dh"], keys["auth"]
    )
    assert await push.send(subscription, {}, ttl_s=60) == "retry"
    await push.aclose()


# --- The settings ---------------------------------------------------------------------


def _settings(**values: str) -> Settings:
    base = make_test_settings().model_dump()
    return Settings(_env_file=None, **{**base, "PUSH_PROVIDER": "webpush", **values})


PUBLIC = vapid_public_key(vapid_private_key(AS_PRIVATE))


def test_web_push_starts_with_a_matching_pair_and_a_subject() -> None:
    settings = _settings(
        VAPID_PRIVATE_KEY=AS_PRIVATE, VAPID_PUBLIC_KEY=PUBLIC, VAPID_SUBJECT=SUBJECT
    )
    assert settings.PUSH_PROVIDER == "webpush"


def test_web_push_names_what_is_missing() -> None:
    with pytest.raises(ValidationError) as caught:
        _settings(VAPID_PRIVATE_KEY=AS_PRIVATE)
    assert "VAPID_PUBLIC_KEY, VAPID_SUBJECT" in str(caught.value)


@pytest.mark.parametrize(
    ("values", "says"),
    [
        ({"VAPID_PRIVATE_KEY": "AAAA"}, "VAPID_PRIVATE_KEY must be"),
        (
            {"VAPID_PUBLIC_KEY": b64url_encode(b"\x04" + bytes(64))},
            "isn't VAPID_PRIVATE_KEY's",
        ),
        ({"VAPID_SUBJECT": "push@example.com"}, "VAPID_SUBJECT must be"),
    ],
)
def test_a_wrong_key_or_subject_is_refused_without_its_value(
    values: dict[str, str], says: str
) -> None:
    good = {
        "VAPID_PRIVATE_KEY": AS_PRIVATE,
        "VAPID_PUBLIC_KEY": PUBLIC,
        "VAPID_SUBJECT": SUBJECT,
    }
    with pytest.raises(ValidationError) as caught:
        _settings(**{**good, **values})
    message = str(caught.value)
    assert says in message
    assert AS_PRIVATE not in message


# --- Push off (D-856, amended; D-857) ---------------------------------------------

INFRA = Path(__file__).resolve().parents[4] / "infra"


def _deployed(env: str, **values: str) -> Settings:
    """Everything staging or production needs, push aside (test_config's way)."""
    base = make_test_settings().model_dump()
    everything = {
        **base,
        "ENV": env,
        "REDIS_URL": "rediss://default:x@redis.example:6379/0",
        "CLIENT_IP_HEADER": "Fly-Client-IP",
        "AUTH_PHONE_PROVIDER": "firebase",
        "FIREBASE_PROJECT_ID": "velora-test",
        "SMS_PROVIDER": "msg91",
        "PAYMENTS_PROVIDER": "razorpay",
        "MODERATION_PROVIDER": "sightengine",
        "FACEMATCH_PROVIDER": "sface",
        "STORAGE_PROVIDER": "s3",
        **r2_settings(),
        **random_keys(),
        **values,
    }
    return Settings(_env_file=None, **everything)  # type: ignore[arg-type]


@pytest.mark.parametrize("env", ["staging", "production"])
def test_push_off_starts_outside_local_with_no_keys(env: str) -> None:
    settings = _deployed(env, PUSH_PROVIDER="off")
    assert (settings.PUSH_PROVIDER, settings.VAPID_PRIVATE_KEY) == ("off", "")
    assert isinstance(build_providers(settings).push, NoPush)


def test_push_off_serves_no_key_even_with_one_set() -> None:
    settings = make_test_settings().model_copy(
        update={"PUSH_PROVIDER": "off", "VAPID_PUBLIC_KEY": PUBLIC}
    )
    with pytest.raises(AppError) as refused:
        service.push_key(settings)
    assert refused.value.code == "NOT_FOUND"


async def test_push_off_sends_nothing() -> None:
    _, keys = browser_keys()
    subscription = PushSubscription(
        "https://fcm.googleapis.com/x", keys["p256dh"], keys["auth"]
    )
    assert await NoPush().send(subscription, {"kind": "match"}, ttl_s=60) == "gone"


@pytest.mark.parametrize(
    "name", ["fly.api.toml", "fly.worker.toml", "fly.api.production.toml"]
)
def test_push_stays_off_everywhere_until_d857_is_decided(name: str) -> None:
    """The founder, 9 October 2026: push off everywhere until D-857 is given in
    their own words. Turning it on changes this test with the file (P-755)."""
    with (INFRA / name).open("rb") as f:
        env = tomllib.load(f)["env"]
    assert env["PUSH_PROVIDER"] == "off"
