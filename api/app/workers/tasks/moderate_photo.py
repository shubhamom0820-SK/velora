"""`moderate_photo`: a public, private or face photo, re-encoded, scored and
decided (T-4.4; the face photo from T-4.12); `photos.service.moderate` does the
work.

`photos.service.complete` queues it with the photo's id and `image_type`, the
type its bytes were then, under the job id `moderate_photo:{id}`, so a photo
has one at a time. The job judges the bytes again (D-089), so `image_type` is
only what `complete` saw.

A storage or Sightengine failure is tried again, 20 and then 40 seconds on. The
third logs at error level and leaves the photo pending (Claude's default in
Sprint 4's Phase 1, which the founder didn't override): nothing approves a photo
nobody checked. Logs name the photo by its id, never a key or a URL (rule 15).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from arq import Retry

from app.modules.photos import service as photos_service

log = structlog.get_logger(__name__)

MODERATE_TRIES: Final = 3
FIRST_RETRY_IN: Final = timedelta(seconds=20)


async def moderate_photo(
    ctx: Mapping[str, Any], *, photo_id: str, image_type: str | None = None
) -> str:
    try:
        return await photos_service.moderate(
            ctx["sessionmaker"],
            UUID(photo_id),
            storage=ctx["storage"],
            moderation=ctx["moderation"],
            queue=ctx["queue"],
            settings=ctx["settings"],
        )
    except photos_service.TryAgain as failure:
        job_try: int = ctx.get("job_try", 1)
        if job_try < MODERATE_TRIES:
            log.warning(
                failure.event, photo_id=photo_id, job_try=job_try, why=str(failure)
            )
            raise Retry(defer=FIRST_RETRY_IN * 2 ** (job_try - 1)) from None
        log.error(failure.event, photo_id=photo_id, job_try=job_try, why=str(failure))
        return "failed: left as it was"
