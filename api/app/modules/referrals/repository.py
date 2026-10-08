"""SQL for referrals (T-8.6). No rules here: the service decides."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Row, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.referrals.models import Referral
from app.modules.users.models import User


async def owner_of(session: AsyncSession, code: str) -> Row[Any] | None:
    """Whose code this is, as typed: `referral_code` is citext, so case is
    ignored, and the format is never checked (the seed's readable codes)."""
    return (
        await session.execute(
            select(User.id, User.onboarding_step, User.status).where(
                User.referral_code == code
            )
        )
    ).one_or_none()


async def number_was_referred(session: AsyncSession, phone_hash: str) -> bool:
    """Whether any account this number ever had was a referee (D-691): an
    erased account keeps its `phone_hash` (D-051) and its referral (D-503)."""
    referred = await session.scalar(
        select(
            exists()
            .where(Referral.referee_id == User.id)
            .where(User.phone_hash == phone_hash)
        )
    )
    return bool(referred)


async def add(session: AsyncSession, *, referee_id: UUID, referrer_id: UUID) -> None:
    session.add(Referral(referee_id=referee_id, referrer_id=referrer_id))
    await session.flush()


async def pending_for_update(
    session: AsyncSession, referee_id: UUID
) -> Referral | None:
    """The referee's referral, locked until the transaction ends, if it hasn't
    been rewarded: two triggers at once take turns, and the second finds it
    done."""
    referral: Referral | None = await session.scalar(
        select(Referral)
        .where(Referral.referee_id == referee_id, Referral.rewarded_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return referral


async def standing_of(
    session: AsyncSession, user_ids: list[UUID]
) -> dict[UUID, Row[Any]]:
    """Each user's gender and status, as the reward reads them."""
    rows = await session.execute(
        select(User.id, User.gender, User.status).where(User.id.in_(user_ids))
    )
    return {row.id: row for row in rows}


async def counts(session: AsyncSession, referrer_id: UUID) -> tuple[int, int]:
    """How many this user referred, and how many of those were rewarded."""
    row = (
        await session.execute(
            select(
                func.count(),
                func.count(Referral.rewarded_at),
            ).where(Referral.referrer_id == referrer_id)
        )
    ).one()
    return row[0], row[1]
