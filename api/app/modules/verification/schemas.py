"""Verification: starting one, submitting its selfie, reading how it went
(T-4.5)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import ReviewStatus


class SubmitSelfie(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A selfie uploaded through `POST /photos/upload-url` with kind `selfie`.
    photo_id: UUID


class Verification(BaseModel):
    """A verification as its owner sees it. Never a number, a link or the
    selfie itself: how closely the faces matched stays on the server, so the
    answer can't be used to tune an impostor's next try (D-263)."""

    id: UUID
    # pending, approved or rejected. Pending and not `submitted`: waiting for
    # its selfie; pending and `submitted`: being compared.
    status: ReviewStatus
    submitted: bool
    # Why it was rejected, from a list; anything unlisted reads `other`.
    reject_reason: str | None
    # Selfies that may still be submitted in the next 24 hours.
    attempts_left: int
