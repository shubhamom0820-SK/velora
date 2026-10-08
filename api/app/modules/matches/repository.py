"""SQL for matches (T-6.4). No rules here: the services decide."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Uuid, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matches.models import Match


async def match_pair(session: AsyncSession, a: UUID, b: UUID) -> UUID:
    """The pair's match, made if there is none: one row per pair, ordered by
    the database's own comparison (`pair_ordered`), never Python's."""
    one, two = literal(a, Uuid), literal(b, Uuid)
    low, high = func.least(one, two), func.greatest(one, two)
    made: UUID | None = await session.scalar(
        insert(Match)
        .values(user_low=low, user_high=high)
        .on_conflict_do_nothing(index_elements=[Match.user_low, Match.user_high])
        .returning(Match.id)
    )
    if made is not None:
        return made
    found = await session.scalar(
        select(Match.id).where(Match.user_low == low, Match.user_high == high)
    )
    assert found is not None
    return found
