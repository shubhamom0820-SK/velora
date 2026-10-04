"""SQL for prices: `action_prices` (wallet/models.py). No rules here: the
service decides what a row means."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wallet.models import ActionPrice


async def price_row(session: AsyncSession, action: str) -> tuple[int, bool] | None:
    """The row's `(credits, active)`, read now, or None if there is no row."""
    row = (
        await session.execute(
            select(ActionPrice.credits, ActionPrice.active).where(
                ActionPrice.action == action
            )
        )
    ).one_or_none()
    return None if row is None else (row.credits, row.active)


async def active_prices(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(ActionPrice.action, ActionPrice.credits)
        .where(ActionPrice.active.is_(True))
        .order_by(ActionPrice.action)
    )
    return dict(rows.tuples().all())
