"""The panel's rules (T-9.5, D-920 to D-929): who may do what, and how far.

Every `/admin/*` route carries its own `require_role(...)` (P-30): the web's
gate is UX, never protection (D-024). These say what a moderator may do beside
an admin, and the limits every action is held to.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Final

from app.core.enums import PhotoKind, ReportStatus, Role, UserStatus
from app.core.providers.sms import mask_phone

STAFF: Final = (Role.MODERATOR, Role.ADMIN)

# A reason or note staff write: long enough to say why, kept in audit_log
# (D-921, D-924). The same bounds everywhere, so one field reads one way.
REASON_MIN: Final = 10
REASON_MAX: Final = 500

# A report waits at most a day for a human (P-761: the report sheet says so).
REPORT_SLA: Final = timedelta(hours=24)

# A grant or correction moves at most this many Velas at once (D-923).
MAX_DELTA: Final = 1000

# The detail page's lists: the newest this many of each.
DETAIL_LIMIT: Final = 50

# Only these kinds reach the panel. Never a selfie or the face photo
# (`verification`): D-264 keeps them behind Fly's login, and the founder kept
# both out (D-925). A route asked about one answers `NOT_FOUND`.
PANEL_PHOTO_KINDS: Final = frozenset({PhotoKind.PUBLIC, PhotoKind.PRIVATE})


class ReportAction(StrEnum):
    """`reports.action`'s values, the database's check (03-SCHEMA)."""

    NONE = "none"
    WARN = "warn"
    FREEZE = "freeze"
    BAN = "ban"


# D-921: dismissed when nothing was done, actioned otherwise. A warning is
# recorded only: nobody is told (no notification kind exists for it).
REPORT_STATUS: Final = {
    ReportAction.NONE: ReportStatus.DISMISSED,
    ReportAction.WARN: ReportStatus.ACTIONED,
    ReportAction.FREEZE: ReportStatus.ACTIONED,
    ReportAction.BAN: ReportStatus.ACTIONED,
}


class StatusTarget(StrEnum):
    """What `POST /admin/users/{id}/status` may set: freeze, ban, or lift
    either back to active."""

    ACTIVE = "active"
    FROZEN = "frozen"
    BANNED = "banned"


# D-922: a moderator may freeze; ban, unban and unfreeze are an admin's alone.
ADMIN_ONLY: Final = frozenset({StatusTarget.BANNED, StatusTarget.ACTIVE})

# Who a freeze reaches: those who can sign in, as T-9.2's automatic one (D-902).
# A deleted account is left to its erasure; a banned one is banned.
FREEZABLE: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})

# Who a ban reaches as a status: anyone not banned and not erased. A deleted
# account inside its 29 days is banned too, which stops its erasure and keeps
# its data (P-401, D-929); an erased one is banned by its number alone, since
# its row can't leave `deleted` (`ck_users_anonymised_is_deleted`).
BANNABLE: Final = frozenset(
    {UserStatus.ACTIVE, UserStatus.PAUSED, UserStatus.FROZEN, UserStatus.DELETED}
)

# A ban's row in `banned_identities`: the only reason a lift may touch (D-922).
BAN_REASON: Final = "ban"


def may(role: Role, target: StatusTarget) -> bool:
    """Whether `role` may set `target` (D-922)."""
    return role is Role.ADMIN or target not in ADMIN_ONLY


def masked(phone: str) -> str:
    """A moderator's view of a number (D-927): `+91******5678`, the fake SMS's
    own mask. Search still takes only the whole number (D-061)."""
    return mask_phone(phone)
