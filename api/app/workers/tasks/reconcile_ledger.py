"""`reconcile_ledger`: every balance checked against the sum of its ledger,
once a day (T-9.9, D-940).

The cron runs it at 03:00 UTC, 08:30 IST, half an hour before
`log_turnover`. Each mismatch is a `wallet.ledger_mismatch` line at error
level, which T-9.12 forwards to the alert channel with every other error line.

Read-only, so a retry or a second run in a day only logs the lines again. The
worker's context carries `sessionmaker`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.wallet import service as wallet_service

# 03:00 UTC is 08:30 IST: a working hour, so a mismatch is read the same day.
RUN_AT_UTC = (3, 0)


async def reconcile_ledger(ctx: Mapping[str, Any]) -> int:
    async with ctx["sessionmaker"]() as session:
        found = await wallet_service.reconcile(session)
    return len(found)
