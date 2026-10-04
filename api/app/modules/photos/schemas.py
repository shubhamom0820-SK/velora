"""Photos: asking to upload, and saying the upload is done (T-4.2)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PhotoKind, ReviewStatus


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PhotoKind
    # Public photos only: the slot, 0 to 5, where 0 is the main one.
    position: int | None = Field(default=None, ge=0, le=5)
    # What the browser says it will send. Signed into the upload, and used for
    # a clearer refusal; the bytes decide what it is (D-089).
    content_type: str = Field(max_length=100)


class UploadUrl(BaseModel):
    photo_id: UUID
    put_url: str
    # Send exactly these with the PUT: the signature covers them.
    headers: dict[str, str]


class Photo(BaseModel):
    """A photo as its owner sees it, and where to view it: an approved public
    photo at the CDN, anything else by a 10-minute signed link to the private
    copy; `None` once its file is gone (a refused upload)."""

    id: UUID
    kind: PhotoKind
    position: int | None
    status: ReviewStatus
    reject_reason: str | None
    url: str | None


class PhotoOrder(BaseModel):
    """Every live public photo, in the order wanted: the first is the main one."""

    model_config = ConfigDict(extra="forbid")

    photo_ids: list[UUID] = Field(min_length=1, max_length=6)
