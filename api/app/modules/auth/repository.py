"""SQL for sign-in. No rules here: the services decide."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
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


async def session_by_token_hash_for_update(
    session: AsyncSession, token_hash: str
) -> Session | None:
    """The session a refresh token belongs to, its row locked until the
    transaction ends: two refreshes presenting one token take turns, so only
    one can rotate it."""
    row: Session | None = await session.scalar(
        select(Session).where(Session.token_hash == token_hash).with_for_update()
    )
    return row


async def revoke_family(
    session: AsyncSession, *, user_id: UUID, family_id: UUID, at: datetime
) -> None:
    """Revoke every live session of a family. Filtered by user as well as
    family, so the partial index on live sessions per user serves it."""
    await session.execute(
        update(Session)
        .where(
            Session.user_id == user_id,
            Session.family_id == family_id,
            Session.revoked_at.is_(None),
        )
        .values(revoked_at=at)
    )


async def revoke_every_session(
    session: AsyncSession, *, user_id: UUID, at: datetime
) -> None:
    """Revoke every live session of the user, every family: five wrong PINs
    (D-069). Each one's access token still works for up to 15 minutes (D-067)."""
    await session.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=at)
    )


async def sign_ins_since(session: AsyncSession, user_id: UUID, since: datetime) -> int:
    """How many session families of `user_id`'s, still signed in, began from
    `since` on: their sign-ins (T-9.2, D-903). Only live ones, so the partial
    index on live sessions serves it; a family signed out before this one
    began isn't counted."""
    found = await session.scalar(
        select(func.count(Session.family_id.distinct())).where(
            Session.user_id == user_id,
            Session.revoked_at.is_(None),
            Session.auth_time >= since,
        )
    )
    return int(found or 0)
