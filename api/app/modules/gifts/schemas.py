"""Gifts — the requests and responses (04-API.md, T-8.9, D-652)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page
from app.modules.pricing.schemas import ShownPrice
from app.modules.threads.schemas import CardLite

GIFT_ID_MAX = 64


class Gift(BaseModel):
    """One gift on sale: its price in Velas is the row's (D-016, D-252)."""

    id: str
    label: str
    asset: str
    credits: int


class GiftCatalogue(BaseModel):
    """`GET /gifts` (D-652): the gifts, and what this man has left of the
    week's free sends (D-231, D-650). A woman sends none, so both are null."""

    gifts: list[Gift]
    free_sends_left: int | None
    # The next Monday 00:00 IST, when the free sends come back.
    free_sends_reset_at: datetime | None


class SendGiftRequest(BaseModel):
    """Who and which gift. The price is never the browser's (rule 6): only
    what the screen showed, compared and never charged (P-56, D-600)."""

    model_config = ConfigDict(extra="forbid")

    recipient_id: UUID
    gift_id: str = Field(min_length=1, max_length=GIFT_ID_MAX)
    # 0 while a free send is left this week, else the gift's price.
    shown_price: ShownPrice = 0


class GiftSend(BaseModel):
    """A gift as its sender sees it: what he paid included."""

    id: UUID
    gift_id: str
    recipient_id: UUID
    credits_charged: int
    thread_id: UUID | None
    created_at: datetime


class ReceivedGift(BaseModel):
    """A gift as she sees it: who sent it, never what he paid (D-652)."""

    id: UUID
    gift_id: str
    sender: CardLite
    created_at: datetime


class ReceivedGiftPage(Page[ReceivedGift]):
    """`Page<ReceivedGift>`: newest first, by `(created_at, id)`."""


class GiftCount(BaseModel):
    gift_id: str
    count: int


class GiftCounts(BaseModel):
    """`GET /users/{id}/gifts`: how many of each, never from whom. Empty when
    she has turned `show_gifts` off, to everyone but herself."""

    counts: list[GiftCount]
