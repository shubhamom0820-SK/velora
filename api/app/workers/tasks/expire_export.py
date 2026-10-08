"""`expire_export`: an export's file deleted once its link has expired, 24
hours after it was ready (T-9.6, D-502); `account.service.expire_export` does
the work, reading the deletion back.

Queued by `export_data` with that delay. A file that won't go is tried again
three times, a minute apart; past that, the daily `erase_accounts` job finds
the export and tries once a day. Logs name the export by its id (rule 15).
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

EXPIRE_TRIES: Final = 4
RETRY_IN: Final = timedelta(minutes=1)


async def expire_export(ctx: Mapping[str, Any], *, export_id: str) -> str:
    try:
        return await account_service.expire_export(
            ctx["sessionmaker"],
            export_id=UUID(export_id),
            storage=ctx["storage"],
            settings=ctx["settings"],
        )
    except Exception as error:  # noqa: BLE001 — a file that won't go is tried again
        job_try: int = ctx.get("job_try", 1)
        if job_try < EXPIRE_TRIES:
            log.warning(
                "export.expire_retrying",
                export_id=export_id,
                job_try=job_try,
                error=type(error).__name__,
            )
            raise Retry(defer=RETRY_IN) from None
        log.error(
            "export.expire_failed", export_id=export_id, error=type(error).__name__
        )
        return "failed: the daily job tries again"
