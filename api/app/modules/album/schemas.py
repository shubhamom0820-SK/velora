"""The private album — the requests and responses (04-API.md, T-8.4, D-732)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import AlbumRequestStatus
from app.core.pagination import Page
from app.modules.pricing.schemas import ShownPrice
from app.modules.threads.schemas import CardLite


class CreateAlbumRequest(BaseModel):
    """Whose album. The price is never the browser's (rule 6): only what the
    screen showed, compared and never charged (P-56, D-600)."""

    model_config = ConfigDict(extra="forbid")

    owner_id: UUID
    # The `album_request` price `/prices` gave, 1 for a man; 0 for a woman.
    shown_price: ShownPrice = 0


class DecideAlbumRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant: bool


class AlbumRequest(BaseModel):
    """A request, as either of its two people sees it: who asked, and never
    what he paid (his wallet's history has that)."""

    id: UUID
    requester: CardLite
    owner_id: UUID
    status: AlbumRequestStatus
    created_at: datetime
    decided_at: datetime | None


class AlbumRequestPage(Page[AlbumRequest]):
    """`Page<AlbumRequest>`: newest first, by `(created_at, id)`."""


class AlbumPhoto(BaseModel):
    # Signed for 10 minutes (D-027): a copy watermarked for the viewer alone.
    url: str


class Album(BaseModel):
    """`GET /users/{id}/album` (D-732): the viewer's latest request to her, or
    null if he never asked, and his copies of her photos, empty unless it is
    granted."""

    status: AlbumRequestStatus | None
    photos: list[AlbumPhoto]
