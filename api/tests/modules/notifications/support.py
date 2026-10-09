"""What the notifications tests share: a browser's subscription, real keys and
all, and reading what was written for a person."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.vapid import b64url_encode, public_bytes
from app.modules.notifications.models import (
    Notification,
    PushOutbox,
    PushSubscription,
)
from tests.modules.discovery.support import bearer

FCM = "https://fcm.googleapis.com/fcm/send/"


def browser_keys() -> tuple[ec.EllipticCurvePrivateKey, dict[str, str]]:
    """A browser's key pair and the `keys` it sends: a real P-256 key, so a
    message encrypted for it can be opened again."""
    private = ec.generate_private_key(ec.SECP256R1())
    return private, {
        "p256dh": b64url_encode(public_bytes(private.public_key())),
        "auth": b64url_encode(os.urandom(16)),
    }


def subscription_body(endpoint: str | None = None) -> dict[str, Any]:
    _, keys = browser_keys()
    return {"endpoint": endpoint or f"{FCM}{uuid.uuid4().hex}", "keys": keys}


async def subscribe(
    client: AsyncClient, token: str, body: dict[str, Any] | None = None
) -> Response:
    return await client.post(
        "/v1/push/subscriptions",
        json=body or subscription_body(),
        headers=bearer(token),
    )


async def subscribed(db: AsyncSession, user_id: uuid.UUID) -> PushSubscription:
    """A subscription written straight to the table, for tests about sending."""
    _, keys = browser_keys()
    row = PushSubscription(
        user_id=user_id,
        endpoint=f"{FCM}{uuid.uuid4().hex}",
        p256dh=keys["p256dh"],
        auth=keys["auth"],
    )
    db.add(row)
    await db.flush()
    return row


async def in_app(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[str, dict[str, Any]]]:
    rows = await db.execute(
        select(Notification.kind, Notification.payload)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at, Notification.id)
        .execution_options(populate_existing=True)
    )
    return [(kind, payload or {}) for kind, payload in rows]


async def outbox(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[str, dict[str, Any]]]:
    rows = await db.execute(
        select(PushOutbox.kind, PushOutbox.payload)
        .where(PushOutbox.user_id == user_id)
        .order_by(PushOutbox.created_at, PushOutbox.id)
        .execution_options(populate_existing=True)
    )
    return [(kind, payload) for kind, payload in rows]


class Sessions:
    """A sessionmaker handing out the test's session, so the sender's writes
    roll back with the test (`tests/workers/test_thread_clock.py`'s way)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        if self.db.in_transaction():
            await self.db.commit()
        events.take_committed(self.db)
        yield self.db
