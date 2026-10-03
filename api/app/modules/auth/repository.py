"""SQL for sign-in. No rules here: the services decide."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BanKind
from app.modules.auth.models import BannedIdentity


async def is_banned(session: AsyncSession, phone_hash: str) -> bool:
    """Whether this number's hash may not sign up again (D-009, D-072)."""
    found = await session.scalar(
        select(BannedIdentity.id)
        .where(
            BannedIdentity.kind == BanKind.PHONE_HASH,
            BannedIdentity.value == phone_hash,
        )
        .limit(1)
    )
    return found is not None
