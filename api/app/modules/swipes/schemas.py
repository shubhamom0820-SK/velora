"""`POST /v1/swipes` — the request and response (04-API.md, T-6.4)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import SwipeDirection
from app.modules.pricing.schemas import ShownPrice


class SwipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    dir: SwipeDirection
    # The price shown for a Super Like (P-56, D-600): compared, never charged.
    shown_price: ShownPrice = 0


class SwipeResult(BaseModel):
    """Whether it made a match, the match's id if so, and how many of today's
    swipes a man has left (null for anyone uncapped, a woman)."""

    matched: bool
    match_id: UUID | None
    swipes_left: int | None
