"""What gifts' tests share: sending one, and reading what it wrote."""

from __future__ import annotations

import uuid
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Role
from app.core.security import make_access_token
from app.modules.gifts.models import GiftSend
from app.modules.notifications.models import Notification
from app.modules.wallet.models import LedgerEntry, Wallet
from tests.conftest import make_test_settings
from tests.modules.discovery.support import bearer


async def send(
    client: AsyncClient,
    token: str,
    recipient: uuid.UUID,
    gift: str = "coffee",
    *,
    shown: int | None = 0,
    key: str | None = None,
    **extra: Any,
) -> Response:
    """`POST /v1/gifts/send`, its key fresh unless given; `shown=None` leaves
    `shown_price` out."""
    body: dict[str, Any] = {"recipient_id": str(recipient), "gift_id": gift, **extra}
    if shown is not None:
        body["shown_price"] = shown
    headers = {**bearer(token), "Idempotency-Key": key or uuid.uuid4().hex}
    return await client.post("/v1/gifts/send", json=body, headers=headers)


async def sent(client: AsyncClient, token: str, *args: Any, **kwargs: Any) -> Any:
    response = await send(client, token, *args, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


async def sends_by(db: AsyncSession, sender_id: uuid.UUID) -> list[GiftSend]:
    rows = await db.scalars(
        select(GiftSend)
        .where(GiftSend.sender_id == sender_id)
        .order_by(GiftSend.created_at, GiftSend.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def ledger(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, int, Any]]:
    """Everything but the test's own grant: (reason, delta, ref_id)."""
    rows = await db.execute(
        select(LedgerEntry.reason, LedgerEntry.delta, LedgerEntry.ref_id)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.reason != "admin_grant")
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
    )
    return [(str(reason), delta, ref) for reason, delta, ref in rows]


async def balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    found = await db.scalar(
        select(Wallet.balance)
        .where(Wallet.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def notes(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, Any]]:
    rows = await db.scalars(select(Notification).where(Notification.user_id == user_id))
    return [(n.kind, n.payload) for n in rows]


async def set_config(db: AsyncSession, key: str, value: int) -> None:
    await db.execute(
        text("UPDATE app_config SET value = CAST(:v AS jsonb) WHERE key = :k"),
        {"k": key, "v": str(value)},
    )


async def price(db: AsyncSession, gift_id: str, credits: int) -> None:
    """Reprice a gift, as an admin's row change would (D-016)."""
    await db.execute(
        text("UPDATE gifts SET credits = :c WHERE id = :g"),
        {"c": credits, "g": gift_id},
    )


def token_for(user_id: uuid.UUID) -> str:
    """A token signed now, by the frozen clock: one from before a jump of
    more than 15 minutes has expired."""
    return make_access_token(
        user_id, Role.USER, make_test_settings(), auth_time=clock.now()
    )
