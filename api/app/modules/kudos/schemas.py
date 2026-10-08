"""Kudos — the requests and responses (04-API.md, T-8.5, D-680)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import Kudos as KudosKind

# Whether the viewer may give kudos to the other person in their Thread (D-790,
# P-580): what the web's prompt reads, so it never shows only to be refused.
KudosState = Literal["too_early", "can_give", "given"]


class GiveKudosRequest(BaseModel):
    """`{to_id, kind}`: one of the four fixed kinds, nothing else (D-007)."""

    model_config = ConfigDict(extra="forbid")

    to_id: UUID
    kind: KudosKind


class KudosGiven(BaseModel):
    """The kudos you just gave."""

    to_id: UUID
    kind: KudosKind
    created_at: datetime


class Kudos(BaseModel):
    """One kind you were given, and how many people gave it. Never who, nor
    when (D-680)."""

    kind: KudosKind
    count: int
