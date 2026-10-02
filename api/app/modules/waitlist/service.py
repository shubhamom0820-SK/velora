"""The waitlist: people outside the launch city asking to hear when Velora opens."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.waitlist import repository


async def join(session: AsyncSession, *, email: str, city: str | None) -> None:
    """Put `email` on the list, once.

    A repeat changes nothing, not even the city, and the caller answers it
    exactly as it answers a new email (D-057). The email is never logged.
    """
    async with session.begin():
        await repository.add_if_new(session, email=email, city=city)
