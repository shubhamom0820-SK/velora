"""SQL for notifications (T-6.4 writes the first). No rules here."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification


def add(
    session: AsyncSession, user_id: UUID, kind: str, payload: dict[str, Any]
) -> None:
    """An in-app notification; T-9.4 lists them and sends the pushes."""
    session.add(Notification(user_id=user_id, kind=kind, payload=payload))
