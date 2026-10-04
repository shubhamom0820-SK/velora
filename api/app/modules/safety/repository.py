"""SQL for safety records. No rules here: the services decide."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.safety.models import FraudEvent


def add_fraud_event(session: AsyncSession, event: FraudEvent) -> None:
    session.add(event)
