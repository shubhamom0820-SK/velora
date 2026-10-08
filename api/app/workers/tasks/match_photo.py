"""`match_photo`: an approved public photo with a face compared with the kept
selfie, for the badge (T-4.12, D-393); `verification.service.match_photo` does
the work.

Queued under the job id `match_photo:{photo id}` by `photos.service` when the
photo is approved with a selfie already kept, or shown from the face photo, and
by `verification.service` for each photo already shown when the selfie is
decided. The result goes in the photo's `moderation` record: a photo that
doesn't match isn't rejected, it just doesn't count toward the badge. Nobody
waits on it, so there is no wake (D-261 is the selfie's).

A storage failure is tried again, 10 and then 20 seconds on. The third logs at
error level and leaves the photo as it is: the badge rests on comparisons that
were made, never on one that wasn't (P-300 is the sweep that would pick it up
later). Logs name the photo by its id, never a key or a URL (rule 15).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final
from uuid import UUID

import structlog
from arq import Retry

from app.modules.verification import service as verification_service

log = structlog.get_logger(__name__)

MATCH_TRIES: Final = 3


async def match_photo(ctx: Mapping[str, Any], *, photo_id: str) -> str:
    try:
        return await verification_service.match_photo(
            ctx["sessionmaker"],
            UUID(photo_id),
            storage=ctx["storage"],
            facematch=ctx["facematch"],
            settings=ctx["settings"],
        )
    except verification_service.TryAgain as failure:
        job_try: int = ctx.get("job_try", 1)
        if job_try < MATCH_TRIES:
            log.warning(
                failure.event, photo_id=photo_id, job_try=job_try, why=str(failure)
            )
            raise Retry(defer=failure.defer * job_try) from None
        log.error(failure.event, photo_id=photo_id, job_try=job_try, why=str(failure))
        return "failed: left as it was"
