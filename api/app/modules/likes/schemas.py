"""`GET /v1/likes`, `GET /v1/likes/count` and `POST /v1/likes/{handle}/reveal`
(T-6.7, D-542): who liked you, and the paid reveal (04-API.md)."""

from __future__ import annotations

from pydantic import BaseModel

from app.core.pagination import Page
from app.modules.discovery.schemas import Card
from app.modules.pricing.schemas import ShownPrice


class LikeCard(BaseModel):
    """Someone who liked or Super Liked you, whom you haven't swiped (D-542).

    A man sees who only once he has revealed them: until then `card` is null,
    and the only picture is the server's blur of their main photo, never their
    name, id or photo. A woman sees everyone (D-002)."""

    # Opaque: what a reveal names. Never the person's id, which would open
    # their profile for free (`GET /users/{id}`).
    handle: str
    # A Super Like.
    is_super: bool
    # The person, once revealed; a woman's always.
    card: Card | None
    # Unrevealed only: their main photo, blurred by the server (never CSS);
    # null with no photo, or while the blur is being made.
    blurred_photo_url: str | None


class LikeCardPage(Page[LikeCard]):
    """`Page<LikeCard>`: newest first."""


class LikesCount(BaseModel):
    """How many people `GET /likes` lists: the header's badge."""

    count: int


class RevealRequest(BaseModel):
    """`POST /likes/{handle}/reveal`'s body (P-56, D-600)."""

    # The reveal's price the screen showed, in Velas: compared with the price
    # now, never charged. A woman's is 0, as her price is.
    shown_price: ShownPrice = 0
