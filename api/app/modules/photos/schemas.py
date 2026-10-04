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
    """A photo as its owner sees it. T-4.3 adds where to view it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: PhotoKind
    position: int | None
    status: ReviewStatus
    reject_reason: str | None
