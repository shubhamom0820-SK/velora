"""The album's rules (T-8.4) that need no database: the re-ask cooldown, the
refusals, and the jobs' ids."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from app.core.errors import AppError
from app.core.queue import WATERMARK_ALBUM

# D-731: after she declines or revokes his request, he can't ask her again
# for this many days. Read fresh at each request.
REASK_KEY: Final = "album_reask_days"

# How long a link to a copy works (D-027's signed GET).
LINK_TTL_S: Final = 600


def may_ask_again(closed_at: datetime | None, now: datetime, days: int) -> bool:
    """Whether a request closed (declined or revoked) at `closed_at` lets the
    same man ask the same woman again at `now`: from `days` after it on."""
    return closed_at is None or now >= closed_at + timedelta(days=days)


def not_allowed(why: str, message: str) -> AppError:
    return AppError("NOT_ALLOWED", message, status=422, details={"why": why})


def recently_declined() -> AppError:
    return not_allowed(
        "recently_declined", "You can't ask to see this album again yet."
    )


def empty_album() -> AppError:
    return not_allowed("empty_album", "There are no private photos to see.")


def already_decided() -> AppError:
    return not_allowed("already_decided", "This request was already answered.")


def not_granted() -> AppError:
    return not_allowed("not_granted", "Only a granted request can be revoked.")


def not_found() -> AppError:
    """One answer for nobody, someone blocked either way, and a request that
    isn't yours to see (04-API: `NOT_FOUND` for a blocked user too)."""
    return AppError("NOT_FOUND", "Not found.", status=404)


# `watermark_album` brings one request's copies in line with its status. Each
# reason to run it has an id of its own: ARQ keeps a finished job's id for an
# hour and refuses the same id again in that time, so a revoke's cleanup must
# never share an id with the grant's rendering.
def grant_job_id(request_id: UUID) -> str:
    return f"{WATERMARK_ALBUM}:{request_id}"


def revoke_job_id(request_id: UUID) -> str:
    return f"{WATERMARK_ALBUM}:{request_id}:revoked"


def photo_job_id(request_id: UUID, photo_id: UUID) -> str:
    """For one photo that came or went after the grant."""
    return f"{WATERMARK_ALBUM}:{request_id}:{photo_id}"
