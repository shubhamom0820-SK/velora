"""`watermark_album`: one album request's watermarked copies brought in line
with it (T-8.4, D-730); `album.service.sync_copies` does the work.

Queued when she grants a request, when she revokes one, when the album shows a
photo its copies lack, and when she removes a private photo, each under a job
id of its own (`album.rules`). While the request is granted, each photo the
album shows gets a copy, rendered from its scored copy (D-700) with the
viewer's `@username`; otherwise every copy is deleted, read back as gone.
Nobody waits on it.

A storage failure is tried again, 10 and then 20 seconds on. The third logs at
error level: a copy left unmade is made on the album's next look; one left
undeleted keeps its row, so the next run, the erasure or D-078's deletion
still finds it. Logs name the request by its id, never a key or a URL
(rule 15).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from arq import Retry

from app.modules.album import service as album_service

log = structlog.get_logger(__name__)

WATERMARK_TRIES: Final = 3
FIRST_RETRY_IN: Final = timedelta(seconds=10)


async def watermark_album(ctx: Mapping[str, Any], *, request_id: str) -> str:
    try:
        return await album_service.sync_copies(
            ctx["sessionmaker"],
            UUID(request_id),
            storage=ctx["storage"],
            settings=ctx["settings"],
        )
    except album_service.TryAgain as failure:
        job_try: int = ctx.get("job_try", 1)
        if job_try < WATERMARK_TRIES:
            log.warning(
                failure.event, request_id=request_id, job_try=job_try, why=str(failure)
            )
            raise Retry(defer=FIRST_RETRY_IN * job_try) from None
        log.error(
            failure.event, request_id=request_id, job_try=job_try, why=str(failure)
        )
        return "failed: left as it was"
