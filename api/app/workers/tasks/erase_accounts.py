"""`erase_accounts`: the daily job, at 03:30 IST, the worker's only cron
(T-9.6, D-500).

It erases every account deleted at least 29 days ago, so each is erased between
day 29 and day 30, within the 30 days `/privacy` promises; then it expires any
data export whose own job left its file behind. One account or export that
fails is logged and left for the next day; the rest go on.

Run by the worker's cron, never queued by the API. ARQ checks its cron at each
poll without asking Redis, so this costs D-091's budget only when it runs: one
enqueue and the job's own few commands, once a day.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import structlog

from app.modules.account import service as account_service

log = structlog.get_logger(__name__)


async def erase_accounts(ctx: Mapping[str, Any]) -> str:
    erased = await account_service.erase_due_accounts(
        ctx["sessionmaker"], storage=ctx["storage"], settings=ctx["settings"]
    )
    expired = await account_service.expire_due_exports(
        ctx["sessionmaker"], storage=ctx["storage"], settings=ctx["settings"]
    )
    log.info("erase_accounts.done", erased=erased, exports_expired=expired)
    return f"erased {erased}, exports expired {expired}"
