"""Kudos — the requests and responses (04-API.md, T-8.5, D-680)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import Kudos as KudosKind


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
