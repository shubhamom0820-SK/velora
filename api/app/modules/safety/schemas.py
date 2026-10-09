"""Reports and blocks — the requests and responses (04-API.md, T-9.1, D-863)."""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.core.enums import ReportReason
from app.core.pagination import Page
from app.modules.threads.schemas import CardLite

# 03-SCHEMA §5: `reports.details` is 500 characters at most (its CHECK).
DETAILS_MAX: Final = 500


class FileReportRequest(BaseModel):
    """`{reported_id, reason, details?, thread_id?, also_block}`. `also_block`
    is said every time, `true` or `false`: a block is never assumed."""

    model_config = ConfigDict(extra="forbid")

    reported_id: UUID
    reason: ReportReason
    details: str | None = Field(default=None, min_length=1, max_length=DETAILS_MAX)
    thread_id: UUID | None = None
    also_block: StrictBool


class ReportFiled(BaseModel):
    """The report you just filed: its id and when. Nothing about what
    moderation does with it, which the reporter is told later, if at all."""

    id: UUID
    created_at: datetime


class BlockRequest(BaseModel):
    """`{user_id}`: whom to block."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class BlockedUser(BaseModel):
    """Someone you block, as a card, and since when. A deleted account is
    `deleted`, with no name, username or photo (D-051, D-500)."""

    user: CardLite
    blocked_at: datetime


class BlockedUserPage(Page[BlockedUser]):
    """`Page<BlockedUser>`: newest block first, by `(created_at, id)`."""


class FiledReport(BaseModel):
    """A report you filed (T-9.8): its reason, when, and whom, as a card. No
    status: what moderation did with it is never said here. Across a block,
    either way, the card has the name and username alone, no photo, badge or
    presence, whoever blocked, so the list never tells which (D-911)."""

    id: UUID
    reason: ReportReason
    created_at: datetime
    reported: CardLite


class FiledReportPage(Page[FiledReport]):
    """`Page<FiledReport>`: newest first, by `(created_at, id)`."""
