"""External services behind interfaces (D-028, T-1.21).

Each provider is a `Protocol` with an in-memory `Fake…` and a real
implementation, chosen by an environment variable in `Settings`. Fakes run only
where `ENV` is `local` — `Settings` refuses to start otherwise (D-045) — and
every test gets them through the `fake_providers` fixture.

Routes reach them with `Depends(get_providers)`; the worker will build its own
with `build_providers` (T-4.4).

Google's keys for Firebase ID tokens (T-3.14) are the exception to choosing by
setting: they are always Google's, because the route that reads them is served
only where `AUTH_PHONE_PROVIDER` is `firebase` (D-085). Elsewhere nothing asks
them for anything, and nothing is fetched. Their fake is the tests' alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from app.core.config import Settings
from app.core.providers.facematch import (
    FaceMatchProvider,
    FakeFaceMatch,
    RekognitionFaceMatch,
)
from app.core.providers.firebase import (
    FakeFirebaseKeys,
    FirebaseKeys,
    GoogleFirebaseKeys,
)
from app.core.providers.moderation import (
    FakeModeration,
    ModerationProvider,
    SightengineModeration,
)
from app.core.providers.payments import FakePayments, PaymentsProvider, RazorpayPayments
from app.core.providers.push import FakePush, PushProvider, WebPush
from app.core.providers.sms import FakeSms, Msg91Sms, SmsProvider, guard_real_sms
from app.core.providers.storage import FakeStorage, S3Storage, StorageProvider


@dataclass(frozen=True)
class Providers:
    sms: SmsProvider
    payments: PaymentsProvider
    moderation: ModerationProvider
    facematch: FaceMatchProvider
    push: PushProvider
    storage: StorageProvider
    firebase_keys: FirebaseKeys


@dataclass(frozen=True)
class FakeProviders:
    """Every provider as its fake, typed as the fake so tests can inspect it:
    `fake_providers.sms.last_code(phone)`."""

    sms: FakeSms = field(default_factory=FakeSms)
    payments: FakePayments = field(default_factory=FakePayments)
    moderation: FakeModeration = field(default_factory=FakeModeration)
    facematch: FakeFaceMatch = field(default_factory=FakeFaceMatch)
    push: FakePush = field(default_factory=FakePush)
    storage: FakeStorage = field(default_factory=FakeStorage)
    firebase_keys: FakeFirebaseKeys = field(default_factory=FakeFirebaseKeys)

    def as_providers(self) -> Providers:
        return Providers(
            sms=self.sms,
            payments=self.payments,
            moderation=self.moderation,
            facematch=self.facematch,
            push=self.push,
            storage=self.storage,
            firebase_keys=self.firebase_keys,
        )


def build_providers(settings: Settings) -> Providers:
    """The providers `settings` selects. A fake SMS echoes codes to the
    terminal: fakes only ever run locally (D-045). A real SMS provider texts
    only `SMS_LOCAL_ALLOWED_TO`'s numbers outside staging and production
    (D-064)."""
    return Providers(
        sms=FakeSms(echo=True)
        if settings.SMS_PROVIDER == "fake"
        else guard_real_sms(Msg91Sms(), settings),
        payments=FakePayments()
        if settings.PAYMENTS_PROVIDER == "fake"
        else RazorpayPayments(),
        moderation=(
            FakeModeration()
            if settings.MODERATION_PROVIDER == "fake"
            else SightengineModeration()
        ),
        facematch=(
            FakeFaceMatch()
            if settings.FACEMATCH_PROVIDER == "fake"
            else RekognitionFaceMatch()
        ),
        push=FakePush() if settings.PUSH_PROVIDER == "fake" else WebPush(),
        storage=(
            FakeStorage()
            if settings.STORAGE_PROVIDER == "fake"
            else S3Storage(settings)
        ),
        firebase_keys=GoogleFirebaseKeys(),
    )


def get_providers(request: Request) -> Providers:
    """FastAPI dependency: the providers this app was built with."""
    providers: Providers = request.app.state.providers
    return providers
