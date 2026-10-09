"""`send_push` (T-9.4, D-850): what waits in `push_outbox`, sent.

Never an ARQ job: run by the worker's wake listener on `wake:send_push`, the
moment a notification's transaction commits, and in the worker's minute
(D-640), for a wake lost on the way. Both may run at once; the outbox's claims
keep them off each other's rows (`notifications/sender.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.notifications import sender


async def run(ctx: Mapping[str, Any]) -> dict[str, int]:
    """Every waiting push, from the worker's context. What became of them."""
    return await sender.send_waiting(ctx["sessionmaker"], ctx["redis"], ctx["push"])
