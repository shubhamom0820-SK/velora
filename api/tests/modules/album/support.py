"""What the album's tests share: asking, answering, and an album to ask for."""

from __future__ import annotations

import io
import uuid
from typing import Any

from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PhotoKind, ReviewStatus
from app.core.providers.storage import FakeStorage
from app.core.storage_keys import scored_key
from app.modules.album.models import AlbumCopy, AlbumRequest
from app.modules.photos.models import Photo
from app.modules.users.models import User
from tests.conftest import make_test_settings
from tests.modules.discovery.support import bearer, photo

SETTINGS = make_test_settings()
PRIVATE = SETTINGS.R2_BUCKET_PRIVATE
REASK = "album_reask_days"


def jpeg(colour: str = "teal", size: tuple[int, int] = (400, 300)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "JPEG")
    return out.getvalue()


async def album_of(
    db: AsyncSession,
    owner: User,
    storage: FakeStorage | None = None,
    *,
    photos: int = 2,
) -> list[Photo]:
    """`photos` approved private photos with scored copies (D-700), oldest
    first, each scored file in `storage` if given: its upload holds other bytes,
    so a copy made from the upload would show."""
    made = []
    for n in range(photos):
        row = await photo(db, owner, kind=PhotoKind.PRIVATE)
        made.append(row)
        if storage is not None:
            assert row.scored_key == scored_key(owner.id, row.id)
            await storage.put_bytes(PRIVATE, row.scored_key, jpeg(), "image/jpeg")
            await storage.put_bytes(
                PRIVATE, row.raw_key, jpeg("red" if n else "blue"), "image/jpeg"
            )
    return made


async def ask(
    client: AsyncClient, token: str, owner: uuid.UUID, *, shown: int | None = 1
) -> Response:
    """`POST /v1/album-requests`; `shown=None` leaves `shown_price` out."""
    body: dict[str, Any] = {"owner_id": str(owner)}
    if shown is not None:
        body["shown_price"] = shown
    return await client.post("/v1/album-requests", json=body, headers=bearer(token))


async def asked(client: AsyncClient, token: str, owner: uuid.UUID, **kw: Any) -> Any:
    response = await ask(client, token, owner, **kw)
    assert response.status_code == 200, response.text
    return response.json()


async def decide(
    client: AsyncClient, token: str, request_id: str, grant: bool
) -> Response:
    return await client.post(
        f"/v1/album-requests/{request_id}/decide",
        json={"grant": grant},
        headers=bearer(token),
    )


async def revoke(client: AsyncClient, token: str, request_id: str) -> Response:
    return await client.post(
        f"/v1/album-requests/{request_id}/revoke", headers=bearer(token)
    )


async def view(client: AsyncClient, token: str, owner: uuid.UUID) -> Response:
    return await client.get(f"/v1/users/{owner}/album", headers=bearer(token))


async def requests_between(
    db: AsyncSession, requester: uuid.UUID, owner: uuid.UUID
) -> list[AlbumRequest]:
    rows = await db.scalars(
        select(AlbumRequest)
        .where(AlbumRequest.requester_id == requester, AlbumRequest.owner_id == owner)
        .order_by(AlbumRequest.created_at, AlbumRequest.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def copies_of(db: AsyncSession, request_id: uuid.UUID) -> list[AlbumCopy]:
    rows = await db.scalars(
        select(AlbumCopy)
        .where(AlbumCopy.request_id == request_id)
        .order_by(AlbumCopy.created_at, AlbumCopy.id)
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def approved_without_score(db: AsyncSession, owner: User) -> Photo:
    """A private photo approved before D-700 wrote scored copies: none."""
    return await photo(db, owner, kind=PhotoKind.PRIVATE, scored=False)


async def removed(db: AsyncSession, row: Photo) -> None:
    """Removed by its owner, as `delete_photo` leaves it."""
    row.status, row.reject_reason = ReviewStatus.REJECTED, "user_deleted"
    await db.flush()
