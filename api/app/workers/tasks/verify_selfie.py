"""`verify_selfie`: a submitted selfie compared with the face photo and
decided (T-4.5, D-391); `verification.service.verify` does the work.

`verification.service.submit` queues it under the job id
`verify_selfie:{id}` and then wakes the worker (D-261), which runs the same
comparison at once (`app/workers/wake.py`). This job is the path that is sure to
run: when the wake decided it first, it finds the verification decided and
does nothing.

Until it can decide, it tries again: a selfie whose submit hasn't committed
yet, the face photo still being moderated, storage down. Its last try records
the reason it was waiting for (the face photo still waiting: `no_photos`; anything
failing: `unavailable`) rather than leave the person waiting on a comparison
that won't come; a selfie never submitted is left alone. Logs name the
verification by its id, never a key or a URL (rule 15).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final
from uuid import UUID

import structlog
from arq import Retry

from app.modules.verification import rules
from app.modules.verification import service as verification_service

log = structlog.get_logger(__name__)

VERIFY_TRIES: Final = 5


async def verify_selfie(ctx: Mapping[str, Any], *, verification_id: str) -> str:
    job_try: int = ctx.get("job_try", 1)
    final: rules.Reason | None = rules.UNAVAILABLE
    try:
        return await run(ctx, UUID(verification_id), via="queue")
    except verification_service.TryAgain as waiting:
        event, why, final = waiting.event, str(waiting), waiting.final
        if job_try < VERIFY_TRIES:
            log.info(event, verification_id=verification_id, job_try=job_try, why=why)
            raise Retry(defer=waiting.defer) from None
    except Exception as error:  # noqa: BLE001 — any failure: the person mustn't wait on it
        event, why = "verification.failed", type(error).__name__
        if job_try < VERIFY_TRIES:
            log.warning(
                event, verification_id=verification_id, job_try=job_try, why=why
            )
            raise Retry(defer=verification_service.STORAGE_FAILED * job_try) from None
    log.error(event, verification_id=verification_id, job_try=job_try, why=why)
    if final is None:
        return "never submitted: left as it is"
    return await verification_service.give_up(
        ctx["sessionmaker"],
        UUID(verification_id),
        final,
        storage=ctx["storage"],
        settings=ctx["settings"],
        via="queue",
    )


async def run(ctx: Mapping[str, Any], verification_id: UUID, *, via: str) -> str:
    """The comparison, with what the worker's context holds: the job's way in
    and the wake's."""
    return await verification_service.verify(
        ctx["sessionmaker"],
        verification_id,
        storage=ctx["storage"],
        facematch=ctx["facematch"],
        queue=ctx["queue"],
        settings=ctx["settings"],
        via=via,
    )
