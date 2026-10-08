"""`POST /v1/swipes` — the request and response (04-API.md, T-6.4)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import SwipeDirection


class SwipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    dir: SwipeDirection


class SwipeResult(BaseModel):
    """Whether it made a match, the match's id if so, and how many of today's
    swipes a man has left (null for anyone uncapped, a woman)."""

    matched: bool
    match_id: UUID | None
    swipes_left: int | None
