"""`log_turnover`: the financial year's aggregate turnover, logged once a day
(D-483, T-8.1).

The cron runs it at 03:30 UTC, 09:00 IST. The line is the year's paid payments,
summed, at info level below ₹15 lakh, warning from ₹15 lakh and error from ₹20
lakh, where GST registration falls due within 30 days (P-350). Until T-9.12
routes it to the alert channel it reaches Fly's logs only (P-381).

Read-only, so a retry or a second run in a day only logs the line again. The
worker's context carries `sessionmaker`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.payments import service as payments_service

# 03:30 UTC is 09:00 IST: a working hour, on the day the line is about.
RUN_AT_UTC = (3, 30)


async def log_turnover(ctx: Mapping[str, Any]) -> str:
    async with ctx["sessionmaker"]() as session:
        level = await payments_service.log_turnover(session)
    return level.value
