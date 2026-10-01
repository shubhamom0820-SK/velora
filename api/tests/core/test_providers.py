"""Provider adapters (T-1.21, D-028, D-045): selection, the fakes, the stubs."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Annotated

import pytest
import structlog
from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from app.core.providers import FakeProviders, Providers, build_providers, get_providers
from app.core.providers.facematch import FaceMatch, FakeFaceMatch, RekognitionFaceMatch
from app.core.providers.moderation import (
    APPROVED,
    FakeModeration,
    ModerationResult,
    SightengineModeration,
)
from app.core.providers.payments import FakePayments, RazorpayPayments
from app.core.providers.push import FakePush, PushSubscription, WebPush
from app.core.providers.sms import FakeSms, Msg91Sms, mask_phone
from app.core.providers.storage import FakeStorage, ObjectNotFound, S3Storage

PHONE = "+919812345678"

_REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "JWT_SECRET": "x",
    "PHONE_PEPPER": "x",
    "PHONE_ENC_KEY": "x",
}
_REAL = {
    "AUTH_PHONE_PROVIDER": "firebase",
    "SMS_PROVIDER": "msg91",
    "PAYMENTS_PROVIDER": "razorpay",
    "MODERATION_PROVIDER": "sightengine",
    "FACEMATCH_PROVIDER": "rekognition",
    "STORAGE_PROVIDER": "s3",
    "PUSH_PROVIDER": "webpush",
}


def _settings(**values: str) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **values})  # type: ignore[arg-type]


# --- Selection --------------------------------------------------------------


def test_local_defaults_build_every_fake() -> None:
    providers = build_providers(_settings(ENV="local"))

    assert isinstance(providers.sms, FakeSms)
    assert isinstance(providers.payments, FakePayments)
    assert isinstance(providers.moderation, FakeModeration)
    assert isinstance(providers.facematch, FakeFaceMatch)
    assert isinstance(providers.push, FakePush)
    assert isinstance(providers.storage, FakeStorage)
    # Locally, the fake SMS shows codes in the terminal so sign-in works.
    assert providers.sms.echo is True


@pytest.mark.parametrize("env", ["local", "staging", "production"])
def test_real_settings_build_every_real_provider(env: str) -> None:
    providers = build_providers(
        _settings(ENV=env, REDIS_URL="rediss://default:x@redis.example:6379/0", **_REAL)
    )

    assert isinstance(providers.sms, Msg91Sms)
    assert isinstance(providers.payments, RazorpayPayments)
    assert isinstance(providers.moderation, SightengineModeration)
    assert isinstance(providers.facematch, RekognitionFaceMatch)
    assert isinstance(providers.push, WebPush)
    assert isinstance(providers.storage, S3Storage)


def test_the_app_is_built_with_its_settings_providers() -> None:
    from app.main import create_app

    app = create_app(_settings(ENV="local"))

    assert isinstance(app.state.providers.payments, FakePayments)


# --- Done-when: a test asserts "an SMS was sent to X" -----------------------


async def test_a_route_sends_sms_through_the_fake(
    app: FastAPI, client: AsyncClient, fake_providers: FakeProviders
) -> None:
    async def send_code(
        providers: Annotated[Providers, Depends(get_providers)],
    ) -> None:
        await providers.sms.send_otp(PHONE, "4821")

    app.add_api_route(
        "/test-only/send-code", send_code, methods=["POST"], status_code=204
    )

    response = await client.post("/test-only/send-code")

    assert response.status_code == 204
    assert fake_providers.sms.last_code(PHONE) == "4821"
    assert fake_providers.sms.echo is False  # tests stay quiet


# --- SMS ---------------------------------------------------------------------


async def test_fake_sms_records_every_code_and_returns_the_last() -> None:
    sms = FakeSms()

    await sms.send_otp(PHONE, "1111")
    await sms.send_otp("+919800000001", "2222")
    await sms.send_otp(PHONE, "3333")

    assert sms.last_code(PHONE) == "3333"
    assert sms.last_code("+919800000009") is None
    assert len(sms.sent) == 3


async def test_fake_sms_echoes_to_the_terminal_with_the_phone_masked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await FakeSms(echo=True).send_otp(PHONE, "4821")

    err = capsys.readouterr().err
    assert "+91******5678" in err
    assert "4821" in err
    assert PHONE not in err


async def test_fake_sms_stays_quiet_without_echo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await FakeSms().send_otp(PHONE, "4821")

    assert capsys.readouterr() == ("", "")


async def test_an_otp_never_reaches_a_log_event() -> None:
    """Rule 15: the echo goes to the terminal, never through the logger."""
    with structlog.testing.capture_logs() as events:
        await FakeSms(echo=True).send_otp(PHONE, "4821")

    assert not any("4821" in json.dumps(event, default=str) for event in events)
    assert not any(PHONE in json.dumps(event, default=str) for event in events)


def test_mask_phone_keeps_country_code_and_last_four() -> None:
    assert mask_phone("+919812345678") == "+91******5678"


# --- Payments ------------------------------------------------------------------


async def test_fake_capture_is_a_signed_razorpay_shaped_webhook() -> None:
    payments = FakePayments()
    order = await payments.create_order(amount_paise=4500, receipt="pay-1")

    webhook = payments.capture(order.id)
    event = json.loads(webhook.body)

    assert payments.verify_webhook(webhook.body, webhook.signature) is True
    assert event["event"] == "payment.captured"
    assert event["payload"]["payment"]["entity"] == {
        "id": "pay_fake_1",
        "order_id": order.id,
        "amount": 4500,
        "currency": "INR",
        "status": "captured",
    }


async def test_fake_webhook_rejects_a_tampered_body_or_signature() -> None:
    payments = FakePayments()
    order = await payments.create_order(amount_paise=4500, receipt="pay-1")
    webhook = payments.capture(order.id)

    tampered = webhook.body.replace(b"4500", b"9900")
    assert payments.verify_webhook(tampered, webhook.signature) is False
    assert payments.verify_webhook(webhook.body, "0" * 64) is False


async def test_fake_can_fake_an_amount_mismatch_and_a_failure() -> None:
    payments = FakePayments()
    order = await payments.create_order(amount_paise=4500, receipt="pay-1")

    mismatch = json.loads(payments.capture(order.id, amount_paise=100).body)
    failed = json.loads(payments.fail(order.id).body)

    assert mismatch["payload"]["payment"]["entity"]["amount"] == 100
    assert failed["event"] == "payment.failed"


async def test_a_webhook_for_an_unknown_order_is_a_test_mistake() -> None:
    with pytest.raises(KeyError, match="order_nope"):
        FakePayments().capture("order_nope")


# --- Moderation --------------------------------------------------------------


async def test_fake_moderation_approves_until_told_to_reject_once() -> None:
    moderation = FakeModeration()

    assert await moderation.check(b"a") == APPROVED
    moderation.next = "reject:minor_suspected"
    assert await moderation.check(b"b") == ModerationResult(
        approved=False, reason="minor_suspected"
    )
    assert await moderation.check(b"c") == APPROVED  # `next` is one-shot
    assert moderation.checked == [b"a", b"b", b"c"]


async def test_fake_moderation_refuses_an_unknown_outcome() -> None:
    moderation = FakeModeration()
    moderation.next = "reject:blurry"

    with pytest.raises(ValueError, match="not 'reject:blurry'"):
        await moderation.check(b"a")


# --- Face match --------------------------------------------------------------


async def test_fake_face_match_matches_until_told_otherwise_once() -> None:
    facematch = FakeFaceMatch()
    two_faces = FaceMatch(similarity=91.0, faces_in_selfie=2)

    assert await facematch.compare(b"selfie", [b"p1"]) == FakeFaceMatch.MATCH
    facematch.next = two_faces
    assert await facematch.compare(b"selfie", [b"p1", b"p2"]) == two_faces
    assert await facematch.compare(b"selfie", [b"p1"]) == FakeFaceMatch.MATCH
    assert facematch.compared[1] == (b"selfie", (b"p1", b"p2"))


# --- Push --------------------------------------------------------------------------


async def test_fake_push_records_and_reports_gone_subscriptions() -> None:
    push = FakePush()
    live = PushSubscription(endpoint="https://push.example/live", p256dh="k", auth="a")
    dead = PushSubscription(endpoint="https://push.example/dead", p256dh="k", auth="a")
    push.gone_endpoints.add(dead.endpoint)

    assert await push.send(live, {"kind": "match"}) == "sent"
    assert await push.send(dead, {"kind": "match"}) == "gone"
    assert push.sent == [(live, {"kind": "match"})]


# --- Storage ------------------------------------------------------------------


async def test_fake_storage_round_trips_copies_and_deletes() -> None:
    storage = FakeStorage()

    await storage.put_bytes("velora-private", "raw/u1/p1", b"jpeg", "image/jpeg")
    await storage.copy("velora-private", "raw/u1/p1", "velora-public", "p/p1.jpg")
    await storage.delete("velora-private", "raw/u1/p1")
    await storage.delete("velora-private", "raw/u1/p1")  # deleting twice is fine

    assert await storage.get_bytes("velora-public", "p/p1.jpg") == b"jpeg"
    with pytest.raises(ObjectNotFound, match="velora-private/raw/u1/p1"):
        await storage.get_bytes("velora-private", "raw/u1/p1")


async def test_fake_storage_presigns_links_that_go_nowhere() -> None:
    storage = FakeStorage()

    put = await storage.presign_put(
        "velora-private", "raw/u1/p1", "image/jpeg", 8_000_000
    )
    get = await storage.presign_get("velora-private", "raw/u1/p1")

    assert put.url.startswith(
        "fake-storage://velora-private/raw/u1/p1?method=PUT&ttl=300"
    )
    assert put.headers == {"Content-Type": "image/jpeg"}
    assert get == "fake-storage://velora-private/raw/u1/p1?method=GET&ttl=600"


# --- The real ones aren't built yet ------------------------------------------------


_STUB_CALLS: list[tuple[str, Callable[[], Awaitable[object] | object], str]] = [
    ("sms", lambda: Msg91Sms().send_otp(PHONE, "1234"), "T-3.2"),
    (
        "payments.create_order",
        lambda: RazorpayPayments().create_order(amount_paise=1, receipt="r"),
        "T-8.1",
    ),
    (
        "payments.verify_webhook",
        lambda: RazorpayPayments().verify_webhook(b"{}", "sig"),
        "T-8.2",
    ),
    ("moderation", lambda: SightengineModeration().check(b"jpeg"), "T-4.4"),
    ("facematch", lambda: RekognitionFaceMatch().compare(b"s", [b"p"]), "T-4.5"),
    ("push", lambda: WebPush().send(PushSubscription("e", "k", "a"), {}), "T-9.4"),
    (
        "storage.presign_put",
        lambda: S3Storage().presign_put("b", "k", "image/jpeg", 1),
        "T-4.1",
    ),
    ("storage.presign_get", lambda: S3Storage().presign_get("b", "k"), "T-4.1"),
    ("storage.get_bytes", lambda: S3Storage().get_bytes("b", "k"), "T-4.1"),
    (
        "storage.put_bytes",
        lambda: S3Storage().put_bytes("b", "k", b"x", "image/jpeg"),
        "T-4.1",
    ),
    ("storage.copy", lambda: S3Storage().copy("b", "k", "b2", "k2"), "T-4.1"),
    ("storage.delete", lambda: S3Storage().delete("b", "k"), "T-4.1"),
]


@pytest.mark.parametrize(
    ("name", "call", "task"), _STUB_CALLS, ids=[c[0] for c in _STUB_CALLS]
)
async def test_real_provider_stubs_name_the_task_that_builds_them(
    name: str, call: Callable[[], Awaitable[object] | object], task: str
) -> None:
    with pytest.raises(
        NotImplementedError, match=rf"arrives? with {re.escape(task)}\."
    ):
        result = call()
        if isinstance(result, Awaitable):
            await result
