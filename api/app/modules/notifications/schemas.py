"""Notifications: requests and responses (04-API.md, T-9.4)."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.core.pagination import Page
from app.modules.notifications import rules

# A subscription's keys (RFC 8291): the browser's P-256 public key,
# uncompressed (65 bytes), and its 16-byte auth secret, each base64url.
P256DH_BYTES = 65
AUTH_BYTES = 16


def b64url_bytes(value: str) -> bytes | None:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return None


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=1, max_length=128)
    auth: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _keys_are_keys(self) -> Self:
        p256dh = b64url_bytes(self.p256dh)
        if p256dh is None or len(p256dh) != P256DH_BYTES or p256dh[0] != 0x04:
            raise ValueError("p256dh is not a P-256 public key")
        auth = b64url_bytes(self.auth)
        if auth is None or len(auth) != AUTH_BYTES:
            raise ValueError("auth is not a 16-byte secret")
        return self


class PushSubscriptionIn(BaseModel):
    """What `PushSubscription.toJSON()` gives, less `expirationTime`. The keys
    are secrets: never logged, never returned (rule 15)."""

    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=1, max_length=rules.ENDPOINT_MAX)
    keys: PushKeys

    @model_validator(mode="after")
    def _a_push_service(self) -> Self:
        if not rules.push_host_allowed(self.endpoint):
            raise ValueError("endpoint is not a known push service")
        return self


class PushSubscriptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=1, max_length=rules.ENDPOINT_MAX)


class PushSubscribed(BaseModel):
    """`POST /push/subscriptions`' answer: the endpoint now held, never its keys."""

    endpoint: str


class PushKey(BaseModel):
    """The VAPID public key, base64url: the `applicationServerKey` a browser
    subscribes with."""

    public_key: str


class Prefs(BaseModel):
    """Which kinds may push (a turned-off kind still shows in the list), and
    `generic_text`, a push with no name in it."""

    match: bool
    message: bool
    like: bool
    knot: bool
    expiry: bool
    balance: bool
    gift: bool
    album: bool
    generic_text: bool


class PrefsPatch(BaseModel):
    """Any of the settings, each only if sent. A field nobody knows is refused,
    and so is a body that changes nothing, as `SettingsPatch` does."""

    model_config = ConfigDict(extra="forbid")

    match: StrictBool | None = None
    message: StrictBool | None = None
    like: StrictBool | None = None
    knot: StrictBool | None = None
    expiry: StrictBool | None = None
    balance: StrictBool | None = None
    gift: StrictBool | None = None
    album: StrictBool | None = None
    generic_text: StrictBool | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if not self.model_fields_set or all(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("send at least one setting, true or false")
        return self


class Notification(BaseModel):
    """One row of the in-app list. `data` is the kind's ids and flags; the web
    turns `kind` into words (en.ts)."""

    id: UUID
    kind: str
    data: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationPage(Page[Notification]):
    pass
