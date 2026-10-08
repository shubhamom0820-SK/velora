"""`export_data`: a copy of a user's own data, written to the private bucket
(T-9.6, D-502); `account.service.write_export` does the work.

Queued under `export_data:{export id}` by `POST /me/export` once its row has
committed. Tried 3 times, 10 and then 20 seconds apart; the last failure marks
the export `failed`, so asking again makes a new one. Its file goes when its
link expires (`expire_export`). Logs name the export by its id, never the
user's number, a key or a link (rule 15).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from arq import Retry

from app.modules.account import service as account_service

log = structlog.get_logger(__name__)

EXPORT_TRIES: Final = 3
RETRY_IN: Final = timedelta(seconds=10)


async def export_data(ctx: Mapping[str, Any], *, export_id: str) -> str:
    try:
        return await account_service.write_export(
            ctx["sessionmaker"],
            export_id=UUID(export_id),
            storage=ctx["storage"],
            settings=ctx["settings"],
            queue=ctx["queue"],
        )
    except Exception as error:  # noqa: BLE001 — any failure is tried again
        job_try: int = ctx.get("job_try", 1)
        if job_try < EXPORT_TRIES:
            log.warning(
                "export.retrying",
                export_id=export_id,
                job_try=job_try,
                error=type(error).__name__,
            )
            raise Retry(defer=RETRY_IN * job_try) from None
        await account_service.fail_export(ctx["sessionmaker"], UUID(export_id))
        return "failed"
