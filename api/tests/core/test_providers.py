"""Provider adapters (T-1.21, D-028, D-045): selection, the fakes, the stubs."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from app.core.providers import FakeProviders, Providers, build_providers, get_providers
from app.core.providers.facematch import FaceMatch, FakeFaceMatch, SFaceFaceMatch
from app.core.providers.moderation import FakeModeration, SightengineModeration
from app.core.providers.payments import FakePayments, RazorpayPayments
from app.core.providers.push import FakePush, PushSubscription, WebPush
from app.core.providers.sms import (
    FakeSms,
    LocallyAllowedSms,
    Msg91Sms,
    SmsRecipientNotAllowed,
    guard_real_sms,
    mask_phone,
)
from app.core.providers.storage import FakeStorage, ObjectNotFound, S3Storage
from tests.conftest import CapturedLogs
from tests.keys import r2_settings, random_keys

PHONE = "+919812345678"

_REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://velora:velora@127.0.0.1:5432/velora",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    **random_keys(),
}
_REAL = {
    "AUTH_PHONE_PROVIDER": "firebase",
    # Path A names its project (D-085).
    "FIREBASE_PROJECT_ID": "velora-test",
    "SMS_PROVIDER": "msg91",
    "PAYMENTS_PROVIDER": "razorpay",
    "MODERATION_PROVIDER": "sightengine",
    "FACEMATCH_PROVIDER": "sface",
    "STORAGE_PROVIDER": "s3",
    **r2_settings(),
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
        _settings(
            ENV=env,
            REDIS_URL="rediss://default:x@redis.example:6379/0",
            CLIENT_IP_HEADER="Fly-Client-IP",
            **_REAL,
        )
    )

    real_sms = (
        providers.sms.real if isinstance(providers.sms, LocallyAllowedSms) else None
    )
    if env == "local":
        # Locally a real SMS provider comes wrapped in D-064's guard.
        assert isinstance(real_sms, Msg91Sms)
    else:
        assert isinstance(providers.sms, Msg91Sms)
    assert isinstance(providers.payments, RazorpayPayments)
    assert isinstance(providers.moderation, SightengineModeration)
    assert isinstance(providers.facematch, SFaceFaceMatch)
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
        await providers.sms.send_otp(PHONE, "482193")

    app.add_api_route(
        "/test-only/send-code", send_code, methods=["POST"], status_code=204
    )

    response = await client.post("/test-only/send-code")

    assert response.status_code == 204
    assert fake_providers.sms.last_code(PHONE) == "482193"
    assert fake_providers.sms.echo is False  # tests stay quiet


# --- SMS ---------------------------------------------------------------------


async def test_fake_sms_records_every_code_and_returns_the_last() -> None:
    sms = FakeSms()

    await sms.send_otp(PHONE, "111111")
    await sms.send_otp("+919800000001", "222222")
    await sms.send_otp(PHONE, "333333")

    assert sms.last_code(PHONE) == "333333"
    assert sms.last_code("+919800000009") is None
    assert len(sms.sent) == 3


async def test_fake_sms_echoes_to_the_terminal_with_the_phone_masked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await FakeSms(echo=True).send_otp(PHONE, "482193")

    err = capsys.readouterr().err
    assert "+91******5678" in err
    assert "482193" in err
    assert PHONE not in err


async def test_fake_sms_stays_quiet_without_echo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await FakeSms().send_otp(PHONE, "482193")

    assert capsys.readouterr() == ("", "")


async def test_an_otp_never_reaches_a_log_event(captured_logs: CapturedLogs) -> None:
    """Rule 15: the echo goes to the terminal, never through the logger. The
    capture's probes prove it was listening, so "not found" means something."""
    await FakeSms(echo=True).send_otp(PHONE, "482193")

    captured_logs.assert_listening()
    assert "482193" not in captured_logs.text
    assert PHONE not in captured_logs.text


def test_mask_phone_keeps_country_code_and_last_four() -> None:
    assert mask_phone("+919812345678") == "+91******5678"


# --- D-064's local guard: a real provider texts only listed numbers ----------


class RecordingSms:
    """A stand-in for a real provider that records what reaches it. Msg91Sms
    has no HTTP client to watch until P-46, so this is what proves the guard
    stops a number before any real provider is called."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent.append((phone, code))


LISTED = "+919812345678"
SEEDED = "+919000000101"  # a profile's number in seed/data.py, maybe someone's


async def test_locally_a_real_provider_is_called_only_for_listed_numbers() -> None:
    real = RecordingSms()
    sms = guard_real_sms(
        real, _settings(ENV="local", SMS_LOCAL_ALLOWED_TO="98123 45678")
    )

    await sms.send_otp(LISTED, "482193")
    with pytest.raises(SmsRecipientNotAllowed) as refused:
        await sms.send_otp(SEEDED, "482193")

    assert real.sent == [(LISTED, "482193")]
    assert "SMS_LOCAL_ALLOWED_TO" in str(refused.value)
    assert "000101" not in str(refused.value)


async def test_locally_with_nothing_listed_no_number_reaches_a_real_provider() -> None:
    real = RecordingSms()
    sms = guard_real_sms(real, _settings(ENV="local"))

    for phone in (LISTED, SEEDED):
        with pytest.raises(SmsRecipientNotAllowed):
            await sms.send_otp(phone, "482193")

    assert real.sent == []


@pytest.mark.parametrize("env", ["staging", "production"])
def test_staging_and_production_text_anyone(env: str) -> None:
    real = RecordingSms()

    sms = guard_real_sms(
        real,
        _settings(
            ENV=env,
            REDIS_URL="rediss://default:x@redis.example:6379/0",
            CLIENT_IP_HEADER="Fly-Client-IP",
            **_REAL,
        ),
    )

    assert sms is real


def test_an_environment_named_later_is_guarded_until_someone_decides() -> None:
    """The guard names where a real provider may text anyone (rule 16). An
    environment nobody has named yet is guarded, so a blacklist (`ENV !=
    "local"`) would fail here: it would wave the new name through."""
    settings = _settings(ENV="local")
    object.__setattr__(settings, "ENV", "preview")

    assert isinstance(guard_real_sms(RecordingSms(), settings), LocallyAllowedSms)


async def test_the_fake_is_never_wrapped_it_sends_nothing() -> None:
    assert isinstance(build_providers(_settings(ENV="local")).sms, FakeSms)


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
#
# Sightengine and its fake are T-4.4's: tests/core/test_moderation.py.


# --- Face match --------------------------------------------------------------


async def test_fake_face_match_matches_until_told_otherwise_once() -> None:
    facematch = FakeFaceMatch()
    two_faces = FaceMatch(model="fake", faces_in_selfie=2, similarities=(None, None))
    one_match = FaceMatch(model="fake", faces_in_selfie=1, similarities=(0.9,))

    assert await facematch.compare(b"selfie", [b"p1"]) == one_match
    facematch.next = two_faces
    assert await facematch.compare(b"selfie", [b"p1", b"p2"]) == two_faces
    assert await facematch.compare(b"selfie", [b"p1"]) == one_match
    assert facematch.compared[1] == (b"selfie", (b"p1", b"p2"))
    facematch.next = "fail"
    with pytest.raises(RuntimeError):
        await facematch.compare(b"selfie", [b"p1"])


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
    ("sms", lambda: Msg91Sms().send_otp(PHONE, "123456"), "P-46"),
    ("push", lambda: WebPush().send(PushSubscription("e", "k", "a"), {}), "T-9.4"),
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
