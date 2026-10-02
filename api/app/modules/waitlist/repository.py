"""SQL for the waitlist. No rules here: the service decides."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.waitlist.models import WaitlistEntry


async def add_if_new(session: AsyncSession, *, email: str, city: str | None) -> None:
    """Insert, or do nothing if the email is already there in any case (citext)."""
    await session.execute(
        insert(WaitlistEntry)
        .values(email=email, city=city)
        .on_conflict_do_nothing(index_elements=[WaitlistEntry.email])
    )
