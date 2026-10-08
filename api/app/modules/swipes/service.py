"""Swipes and matching (T-6.4).

`POST /v1/swipes`: a like, a pass or a Super Like on someone the feed could
show the swiper (D-492), once per pair, ever. Swiping is free (D-098). A Super
Like costs a man its price, through `pricing.charge` and so the wallet's own
`debit()` (CLAUDE.md rule 5), and a woman nothing (D-002). A man's like and
pass count toward his daily cap (`app_config`, the IST day), a Super Like
doesn't (D-492). A like or Super Like back makes the pair's match, and each
of them hears of it: `match.created` on their socket and a notification.

The pair is locked for the transaction, so two people liking each other at
once are one after the other and the second makes the match. The cap's place
is taken before the transaction and given back if the swipe isn't written.
"""

from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, events
from app.core.enums import LedgerReason, SwipeDirection
from app.core.errors import AppError
from app.modules.admin import service as admin_service
from app.modules.discovery import service as discovery_service
from app.modules.matches import repository as matches_repository
from app.modules.notifications import repository as notifications_repository
from app.modules.pricing import service as pricing_service
from app.modules.swipes import counter, repository, rules
from app.modules.swipes.schemas import SwipeResult
from app.modules.users.models import User
from app.modules.wallet.rules import Ref, RefType

MATCH_CREATED = "match.created"
MATCH_NOTIFICATION = "match"


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


def _limit_reached(limit: int, resets_at: str) -> AppError:
    return AppError(
        "SWIPE_LIMIT_REACHED",
        "That's today's swipes. More tomorrow.",
        status=429,
        details={"limit": limit, "resets_at": resets_at},
    )


async def swipe(
    session: AsyncSession,
    redis: Redis,
    user: User,
    target_id: UUID,
    direction: SwipeDirection,
    *,
    config: admin_service.ConfigCache | None = None,
) -> SwipeResult:
    # Read now: a refusal rolls the session back, which expires `user`.
    # Yourself is `NOT_FOUND` like anyone the feed can't show you (`visible_to`).
    user_id = user.id
    day = clock.today_ist()
    capped = rules.capped(user.gender)
    async with session.begin():
        limit = (
            await admin_service.config_int(session, rules.DAILY_CAP_KEY, cache=config)
            if capped
            else None
        )
    took = False
    if limit is not None and rules.counts(direction):
        if await counter.take(redis, user_id, day, limit) is None:
            raise _limit_reached(limit, rules.resets_at(day).isoformat())
        took = True
    try:
        async with session.begin():
            match_id = await _swipe_in(session, user, target_id, direction)
    except BaseException:
        if took:
            await counter.give_back(redis, user_id, day)
        raise
    left = (
        None
        if limit is None
        else max(0, limit - await counter.used(redis, user_id, day))
    )
    return SwipeResult(
        matched=match_id is not None, match_id=match_id, swipes_left=left
    )


async def _swipe_in(
    session: AsyncSession, user: User, target_id: UUID, direction: SwipeDirection
) -> UUID | None:
    """The swipe, its charge and its match, in the caller's transaction: the
    match's id, or None."""
    await repository.lock_pair(session, user.id, target_id)
    viewer = await discovery_service.viewer_of(session, user)
    if not await repository.is_swipeable(session, viewer, target_id):
        raise _not_found()
    if await repository.direction_of(session, user.id, target_id) is not None:
        raise AppError("ALREADY_EXISTS", "You've already swiped on them.", status=409)
    await repository.add(session, user.id, target_id, direction)
    if direction is SwipeDirection.SUPER:
        await pricing_service.charge(
            session, user, LedgerReason.SUPER_LIKE, ref=Ref(RefType.USER, target_id)
        )
    if direction not in rules.LIKES:
        return None
    back = await repository.direction_of(session, target_id, user.id)
    if back not in rules.LIKES:
        return None
    match_id = await matches_repository.match_pair(session, user.id, target_id)
    for one, other in ((user.id, target_id), (target_id, user.id)):
        payload = {"match_id": str(match_id), "user_id": str(other)}
        events.queue(session, one, MATCH_CREATED, payload)
        notifications_repository.add(session, one, MATCH_NOTIFICATION, payload)
    return match_id
