"""Google's keys for Firebase ID tokens (T-3.14, D-085): read from Google's
documented certificate URL, kept for the response's max-age by `core.clock`,
fetched again for a key we don't hold no more than once a minute, and every
failure an outage, never a key. Nothing here reaches Google: httpx's
MockTransport answers in its place, shaped as Google answered on 4 October
2026 (a JSON map of key ID to PEM certificate, `Cache-Control: public,
max-age=23606, must-revalidate, no-transform`)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from types import ModuleType

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from app.core.providers.firebase import (
    CERTS_URL,
    DEFAULT_MAX_AGE,
    FirebaseKeysUnavailable,
    GoogleFirebaseKeys,
)

START = datetime(2026, 10, 4, 6, 30, tzinfo=UTC)
GOOGLES_CACHE_CONTROL = "public, max-age=23606, must-revalidate, no-transform"

Handler = Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]


def _certificate(key: rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey) -> str:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "securetoken")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(START - timedelta(days=1))
        .not_valid_after(START + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM).decode()


KEY_A = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY_B = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CERT_A, CERT_B = _certificate(KEY_A), _certificate(KEY_B)


class Google:
    """Answers as Google does, from `listed`, and counts what it was asked."""

    def __init__(
        self,
        listed: dict[str, str] | None = None,
        *,
        cache_control: str | None = GOOGLES_CACHE_CONTROL,
    ) -> None:
        self.listed = {"a": CERT_A} if listed is None else listed
        self.cache_control = cache_control
        self.requests: list[httpx.Request] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        headers = {"content-type": "application/json; charset=UTF-8"}
        if self.cache_control is not None:
            headers["cache-control"] = self.cache_control
        return httpx.Response(200, headers=headers, content=json.dumps(self.listed))


def _keys(handler: Handler) -> GoogleFirebaseKeys:
    return GoogleFirebaseKeys(transport=httpx.MockTransport(handler))


def _same(found: rsa.RSAPublicKey | None, key: rsa.RSAPrivateKey) -> bool:
    return (
        found is not None
        and found.public_numbers() == key.public_key().public_numbers()
    )


async def test_reads_googles_documented_url_and_its_certificates(
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    google = Google({"a": CERT_A, "b": CERT_B})
    keys = _keys(google)

    assert _same(await keys.key_for("a"), KEY_A)
    assert _same(await keys.key_for("b"), KEY_B)
    assert [str(r.url) for r in google.requests] == [CERTS_URL]
    assert google.requests[0].method == "GET"


async def test_nothing_is_fetched_before_the_first_token() -> None:
    google = Google()
    _keys(google)

    assert google.requests == []


async def test_keys_are_kept_for_googles_max_age_by_our_clock(
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    google = Google()
    keys = _keys(google)

    await keys.key_for("a")
    clock.advance(timedelta(seconds=23605))
    await keys.key_for("a")
    assert len(google.requests) == 1

    clock.advance(timedelta(seconds=1))
    await keys.key_for("a")
    assert len(google.requests) == 2


async def test_without_a_max_age_keys_are_kept_an_hour(clock: ModuleType) -> None:
    clock.freeze(START)
    google = Google(cache_control="public, must-revalidate")
    keys = _keys(google)

    await keys.key_for("a")
    clock.advance(DEFAULT_MAX_AGE - timedelta(seconds=1))
    await keys.key_for("a")
    clock.advance(timedelta(seconds=1))
    await keys.key_for("a")

    assert DEFAULT_MAX_AGE == timedelta(hours=1)
    assert len(google.requests) == 2


async def test_a_key_we_dont_hold_is_fetched_for_at_most_once_a_minute(
    clock: ModuleType,
) -> None:
    """Made-up key IDs can't turn into a stream of requests to Google."""
    clock.freeze(START)
    google = Google()
    keys = _keys(google)
    await keys.key_for("a")

    clock.advance(timedelta(seconds=59))
    assert await keys.key_for("made-up") is None
    assert await keys.key_for("made-up-too") is None
    assert len(google.requests) == 1

    clock.advance(timedelta(seconds=1))
    assert await keys.key_for("made-up") is None
    assert len(google.requests) == 2


async def test_a_key_google_rotated_in_is_found_by_that_fetch(
    clock: ModuleType,
) -> None:
    clock.freeze(START)
    google = Google({"a": CERT_A})
    keys = _keys(google)
    await keys.key_for("a")

    google.listed = {"a": CERT_A, "b": CERT_B}
    clock.advance(timedelta(minutes=1))

    assert _same(await keys.key_for("b"), KEY_B)


async def test_requests_waiting_on_one_fetch_share_it(clock: ModuleType) -> None:
    """The overlap is forced: the first fetch is held open until the second
    lookup is waiting behind it, so a missing lock would show as two fetches."""
    clock.freeze(START)
    release = asyncio.Event()
    google = Google()

    async def held(request: httpx.Request) -> httpx.Response:
        await release.wait()
        return await google(request)

    keys = _keys(held)
    first = asyncio.create_task(keys.key_for("a"))
    second = asyncio.create_task(keys.key_for("a"))
    for _ in range(20):
        await asyncio.sleep(0)
    assert not first.done() and not second.done()
    release.set()

    assert _same(await first, KEY_A) and _same(await second, KEY_A)
    assert len(google.requests) == 1


async def _refuses(handler: Handler) -> None:
    with pytest.raises(FirebaseKeysUnavailable):
        await _keys(handler).key_for("a")


async def test_an_unreachable_google_is_an_outage_not_a_missing_key() -> None:
    async def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    await _refuses(unreachable)


async def test_a_slow_google_is_an_outage() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    await _refuses(slow)


@pytest.mark.parametrize("status", [404, 500, 503])
async def test_an_error_status_is_an_outage(status: int) -> None:
    async def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=json.dumps({"a": CERT_A}))

    await _refuses(failing)


@pytest.mark.parametrize(
    "body",
    [
        b"<html>maintenance</html>",
        b"{}",
        b"[]",
        json.dumps({"a": 1}).encode(),
        json.dumps({"a": "not a certificate"}).encode(),
        json.dumps({"a": CERT_A, "b": "not a certificate"}).encode(),
        json.dumps(
            {"a": _certificate(ec.generate_private_key(ec.SECP256R1()))}
        ).encode(),
    ],
    ids=[
        "html",
        "empty map",
        "a list",
        "a number",
        "garbage",
        "one bad of two",
        "not an RSA key",
    ],
)
async def test_a_body_that_isnt_googles_certificates_is_an_outage(body: bytes) -> None:
    async def odd(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    await _refuses(odd)


async def test_a_bad_answer_replaces_no_keys(clock: ModuleType) -> None:
    """Keys go stale, the refetch answers garbage: nothing of it is taken, and
    the next lookup fetches again rather than trusting what it couldn't read."""
    clock.freeze(START)
    google = Google()
    answers: list[httpx.Response | None] = [None]

    async def flaky(request: httpx.Request) -> httpx.Response:
        planned = answers.pop(0) if answers else None
        return planned if planned is not None else await google(request)

    keys = _keys(flaky)
    await keys.key_for("a")
    clock.advance(timedelta(seconds=23606))
    answers.append(httpx.Response(200, content=b"<html>maintenance</html>"))

    with pytest.raises(FirebaseKeysUnavailable):
        await keys.key_for("a")
    assert _same(await keys.key_for("a"), KEY_A)
