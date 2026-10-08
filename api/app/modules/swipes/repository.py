"""SQL for swipes (T-6.4). No rules here: the service decides."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SwipeDirection
from app.modules.discovery.repository import Viewer, visible_to
from app.modules.profiles.models import Profile
from app.modules.swipes.models import Swipe
from app.modules.users.models import User

# The advisory lock's first key, meaning "a swipe pair"; the second is the
# ordered pair's hash. P-55's slots lock on 55, fresh men's numbers on 97.
PAIR_LOCK = 64


async def lock_pair(session: AsyncSession, a: UUID, b: UUID) -> None:
    """Hold the pair until this transaction ends, whoever swipes whom: two
    people liking each other at once are then one after the other, and the
    second sees the first's like. A hash collision only serialises two
    unrelated pairs a moment longer."""
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock(:lock, hashtext("
            "least(CAST(:a AS uuid), CAST(:b AS uuid))::text"
            " || greatest(CAST(:a AS uuid), CAST(:b AS uuid))::text))"
        ),
        {"lock": PAIR_LOCK, "a": a, "b": b},
    )


async def is_swipeable(session: AsyncSession, viewer: Viewer, target_id: UUID) -> bool:
    """Whether the feed could ever show `target_id` to `viewer`: discovery's
    `visible_to`, mutual, without the radius or swipes (D-492)."""
    found = await session.scalar(
        select(User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(User.id == target_id, *visible_to(viewer, mutual=True))
    )
    return found is not None


async def direction_of(
    session: AsyncSession, swiper_id: UUID, target_id: UUID
) -> SwipeDirection | None:
    found: SwipeDirection | None = await session.scalar(
        select(Swipe.dir).where(
            Swipe.swiper_id == swiper_id, Swipe.target_id == target_id
        )
    )
    return found


async def add(
    session: AsyncSession, swiper_id: UUID, target_id: UUID, direction: SwipeDirection
) -> None:
    session.add(Swipe(swiper_id=swiper_id, target_id=target_id, dir=direction))
    await session.flush()
