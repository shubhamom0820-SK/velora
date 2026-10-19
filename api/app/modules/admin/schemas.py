"""The panel's request and response bodies (04-API "Admin", T-9.5).

Staff see what moderation needs and no more: never a selfie or the face photo
(D-925), a moderator never the whole phone number (D-927), and never anything
from rule 15's never-log list in an audit row's `meta`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.enums import (
    FraudBand,
    Gender,
    LedgerReason,
    MessageKind,
    OnboardingStep,
    PhotoKind,
    ReportReason,
    ReportStatus,
    ReviewStatus,
    Role,
    ThreadOrigin,
    ThreadStatus,
    UserStatus,
)
from app.core.pagination import Page
from app.modules.admin.rules import (
    MAX_DELTA,
    REASON_MAX,
    REASON_MIN,
    MinorDecision,
    ReportAction,
    StatusTarget,
)

# Why staff did something, kept in audit_log (D-921 to D-924).
Reason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=REASON_MIN, max_length=REASON_MAX
    ),
]


# --- People --------------------------------------------------------------------------


class AdminUserRef(BaseModel):
    """Someone named in another row: a report's two people, a Thread's other."""

    id: UUID
    first_name: str | None
    username: str | None
    status: UserStatus


class AdminUser(BaseModel):
    """An account as staff see it in a list. `erased` once T-9.6's erasure ran:
    its profile is empty, its number's hash kept (D-500)."""

    id: UUID
    first_name: str | None
    username: str | None
    city: str | None
    gender: Gender | None
    age: int | None
    role: Role
    status: UserStatus
    onboarding_step: OnboardingStep
    erased: bool
    deleted_requested_at: datetime | None
    last_active_at: datetime | None
    created_at: datetime


class AdminUserPage(Page[AdminUser]):
    """`Page<AdminUser>`: newest account first, by `(created_at, id)`."""


class AdminPhoto(BaseModel):
    """A public or private photo, never a selfie or the face photo (D-925).
    `reject_reason` is the real one, `minor_suspected` included (D-093);
    `minor_score` the model's, kept below the threshold too (D-101). `url` is
    a 10-minute signed link, or the CDN's for an approved public photo, or none
    once rejected and its file gone."""

    id: UUID
    user_id: UUID
    kind: PhotoKind
    position: int | None
    status: ReviewStatus
    reject_reason: str | None
    minor_score: float | None
    url: str | None
    created_at: datetime


class AdminPhotoPage(Page[AdminPhoto]):
    """`Page<AdminPhoto>`: the moderation queue, oldest first by `(created_at, id)`."""


class AdminFraudEvent(BaseModel):
    signal: str
    weight: int
    meta: dict[str, Any] | None
    created_at: datetime


class AdminFraud(BaseModel):
    """`fraud_scores` and the newest events (D-900). A signal, never a verdict."""

    score: int
    band: FraudBand
    signals: dict[str, Any] | None
    counted_from: datetime | None
    events: list[AdminFraudEvent]


class AdminReport(BaseModel):
    """A report, its two people and when its day is up (D-921, P-761)."""

    id: UUID
    reporter: AdminUserRef
    reported: AdminUserRef
    reason: ReportReason
    details: str | None
    thread_id: UUID | None
    status: ReportStatus
    action: ReportAction | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    due_at: datetime


class AdminReportPage(Page[AdminReport]):
    """`Page<AdminReport>`: oldest first by `(created_at, id)`, a queue."""


class AdminLedgerEntry(BaseModel):
    """A ledger row with its ref, which only staff see (D-077)."""

    id: UUID
    delta: int
    balance_after: int
    reason: LedgerReason
    ref_type: str | None
    ref_id: UUID | None
    created_at: datetime


class AdminThread(BaseModel):
    id: UUID
    other: AdminUserRef
    status: ThreadStatus
    origin: ThreadOrigin
    message_count: int
    last_message_at: datetime | None
    created_at: datetime


class AdminBan(BaseModel):
    """The number's standing ban, if any: `ban` an admin's, `underage` D-072's
    or an admin's underage ban (D-991). `permanent` when it is underage, by its
    row or by the account's record: nothing lifts it."""

    reason: str | None
    created_at: datetime
    permanent: bool


class AdminMinorFlags(BaseModel):
    """A person's possible-minor flags waiting for a human (D-991): two or more
    in 30 days, after any decision on them (D-1050). Each a model's score for
    one photo, oldest first, never the photo (D-093 deleted it)."""

    flags: int
    scores: list[float]
    times: list[datetime]
    first_at: datetime
    last_at: datetime


class AdminUserDetail(BaseModel):
    """`GET /admin/users/{id}`. `phone` in full for an admin, each view
    audited; masked for a moderator; null once erased (D-927). The lists are
    the newest 50 of each."""

    user: AdminUser
    phone: str | None
    phone_masked: bool
    is_verified: bool
    balance: int
    ban: AdminBan | None
    minor_flags: AdminMinorFlags | None
    photos: list[AdminPhoto]
    fraud: AdminFraud | None
    reports_about: list[AdminReport]
    reports_by: list[AdminReport]
    ledger: list[AdminLedgerEntry]
    threads: list[AdminThread]


# --- Actions -------------------------------------------------------------------------


class StatusChange(BaseModel):
    """`frozen` (moderator or admin), `banned` or `active` (admin): D-922."""

    model_config = ConfigDict(extra="forbid")

    status: StatusTarget
    reason: Reason


class MinorDecisionRequest(BaseModel):
    """`adult` and `underage` an admin's, `freeze` staff's (D-1050); the reason
    kept in audit_log (D-991)."""

    model_config = ConfigDict(extra="forbid")

    decision: MinorDecision
    reason: Reason


class CreditsChange(BaseModel):
    """Velas granted (`delta` > 0, `admin_grant`) or taken back (< 0,
    `admin_correction`), at most 1,000 either way (D-923)."""

    model_config = ConfigDict(extra="forbid")

    delta: Annotated[int, Field(ge=-MAX_DELTA, le=MAX_DELTA, strict=True)]
    reason: Reason


class ReportResolution(BaseModel):
    """`none` dismisses; `warn`, `freeze` and `ban` action it (D-921)."""

    model_config = ConfigDict(extra="forbid")

    action: ReportAction
    note: Reason


# The reasons staff reject a photo for, of moderation's own (D-101): never
# `minor_suspected`, the model's, whose deletion D-093 runs.
StaffRejectReason = Literal["nudity", "text_overlay", "other"]


class PhotoDecision(BaseModel):
    """Approve a pending photo, or take down a pending or approved one: which
    of moderation's reasons, and a note saying why, kept in audit_log."""

    model_config = ConfigDict(extra="forbid")

    approve: bool
    reason: StaffRejectReason | None = None
    note: Reason | None = None


# --- Reading a Thread ----------------------------------------------------------------


class AdminMessage(BaseModel):
    """A message as written: `body_raw` where masking changed it, else `body`
    (T-7.3). A voice note's link lasts 10 minutes."""

    id: UUID
    sender_id: UUID | None
    kind: MessageKind
    body: str | None
    masked: bool
    duration_s: int | None
    audio_url: str | None
    created_at: datetime


class AdminMessagePage(Page[AdminMessage]):
    """`Page<AdminMessage>`: oldest first by `(created_at, id)`, everything
    either person cleared included (T-7.8, D-006)."""


# --- The record ----------------------------------------------------------------------


class AuditEntry(BaseModel):
    """An `audit_log` row. `actor_is_system` for the system user (D-905),
    which the web names "System"."""

    id: UUID
    actor_id: UUID
    actor_is_system: bool
    action: str
    target_type: str | None
    target_id: UUID | None
    meta: dict[str, Any] | None
    created_at: datetime


class AuditEntryPage(Page[AuditEntry]):
    """`Page<AuditEntry>`: newest first by `(created_at, id)`."""


class AdminFreeze(BaseModel):
    """An account frozen now (P-800, D-928): `automatic` when the system user
    froze it (T-9.2), with its rule and score; else a person did."""

    user: AdminUser
    frozen_at: datetime | None
    automatic: bool
    rule: str | None
    score: int | None


class AdminFreezePage(Page[AdminFreeze]):
    """`Page<AdminFreeze>`: the newest freeze first."""


class AdminMinorFlag(AdminMinorFlags):
    """A person on the possible-minor list (P-72, D-991)."""

    user: AdminUser


class AdminMinorFlagPage(Page[AdminMinorFlag]):
    """`Page<AdminMinorFlag>`: the newest flag first."""


class AdminRevenue(BaseModel):
    """Paid payments' money in (D-483), never the ledger: an admin's alone."""

    last_7_days_paise: int
    last_30_days_paise: int
    financial_year: str
    financial_year_paise: int


class AdminMetrics(BaseModel):
    """The dashboard's counts (D-926). `revenue` is null for a moderator."""

    users_by_status: dict[UserStatus, int]
    signups_24h: int
    signups_7d: int
    reports_open: int
    oldest_open_report_at: datetime | None
    photos_pending: int
    frozen: int
    claims_open: int
    revenue: AdminRevenue | None
