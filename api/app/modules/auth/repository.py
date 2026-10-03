"""SQL for sign-in. No rules here: the services decide."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BanKind
from app.modules.auth.models import BannedIdentity, Session


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


async def insert_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    family_id: UUID,
    token_hash: str,
    expires_at: datetime,
    auth_time: datetime,
) -> Session:
    """One refresh-token session. No IP address and no user agent: nothing
    reads them, and /privacy lists neither (D-067)."""
    row = Session(
        user_id=user_id,
        family_id=family_id,
        token_hash=token_hash,
        expires_at=expires_at,
        auth_time=auth_time,
    )
    session.add(row)
    await session.flush()
    return row
