"""Settings and data rights: requests and responses (04-API.md, T-9.6)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator


class SettingsPatch(BaseModel):
    """Any of the five privacy switches, each only if sent. A field nobody
    knows is refused rather than ignored, and so is a body that changes
    nothing: a typo in a privacy switch must never look like it worked."""

    model_config = ConfigDict(extra="forbid")

    is_hidden: StrictBool | None = None
    hide_age: StrictBool | None = None
    hide_distance: StrictBool | None = None
    show_kudos: StrictBool | None = None
    show_gifts: StrictBool | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if not self.model_fields_set or all(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("send at least one setting, true or false")
        return self


class DeletionScheduled(BaseModel):
    """`DELETE /me`'s answer: when the account will be erased at the latest.
    Signing in again before then cancels the deletion (D-500)."""

    erase_by: datetime


ExportStatus = Literal["pending", "ready", "failed", "expired"]


class DataExport(BaseModel):
    """A copy of the user's own data (D-502). `url` is a link to the file,
    signed until `expires_at`, only while it is `ready`; otherwise null."""

    id: UUID
    status: ExportStatus
    requested_at: datetime
    expires_at: datetime | None
    url: str | None
