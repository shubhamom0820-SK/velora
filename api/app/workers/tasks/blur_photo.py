"""`blur_photo`: an approved public photo's blurred copy, for Liked you (T-6.7,
D-543); `photos.service.blur` does the work.

Queued under the job id `blur_photo:{photo id}` by `photos.service` when a
public photo is approved, and by `GET /likes` for a main photo approved before
T-6.7 made blurs. Nobody waits on it: until it has run, a man's tile shows no
picture.

A storage failure is tried again, 10 and then 20 seconds on. The third logs at
error level and leaves the photo without a blur; the next `GET /likes` that
needs it queues it again. Logs name the photo by its id, never a key or a URL
(rule 15).
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

BLUR_TRIES: Final = 3
FIRST_RETRY_IN: Final = timedelta(seconds=10)


async def blur_photo(ctx: Mapping[str, Any], *, photo_id: str) -> str:
    try:
        return await photos_service.blur(
            ctx["sessionmaker"],
            UUID(photo_id),
            storage=ctx["storage"],
            settings=ctx["settings"],
        )
    except photos_service.TryAgain as failure:
        job_try: int = ctx.get("job_try", 1)
        if job_try < BLUR_TRIES:
            log.warning(
                failure.event, photo_id=photo_id, job_try=job_try, why=str(failure)
            )
            raise Retry(defer=FIRST_RETRY_IN * job_try) from None
        log.error(failure.event, photo_id=photo_id, job_try=job_try, why=str(failure))
        return "failed: left without a blur"
