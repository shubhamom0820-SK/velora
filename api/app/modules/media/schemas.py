"""`POST /v1/media/voice-upload-url` — the request and response (04-API.md, T-7.9)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VoiceUploadRequest(BaseModel):
    """`{thread_id, content_type}`. The type only decides what the URL is
    signed for; the bytes decide what is accepted, at the send (D-620)."""

    model_config = ConfigDict(extra="forbid")

    thread_id: UUID
    content_type: str = Field(min_length=1, max_length=100)


class VoiceUpload(BaseModel):
    """Where to PUT the recording, for 5 minutes (D-027), with exactly these
    headers; then send it as `kind=voice` with this `media_key`. The message
    it becomes takes `message_id`."""

    message_id: UUID
    media_key: str
    put_url: str
    headers: dict[str, str]
