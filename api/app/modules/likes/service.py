"""Liked you (T-6.7, D-542): who liked or Super Liked you and is still
waiting on your swipe, and the reveal.

A woman sees each of them, free (D-002). A man sees, until he reveals one,
only that someone did, a Super Like or not, and the server's blur of their
main photo: never a name, an id, a username or the photo itself. A reveal is
the `liked_you_reveal` row's price, through `pricing.charge` and so the
wallet's `debit()` (CLAUDE.md rule 5): 1 Vela from 8 October 2026 (P-370),
never a literal. It is paid once per pair, held twice: the reveal's row goes
in first and only the request that wrote it asks to pay; and the wallet keys
the debit by the man, the reason and the other person (D-077), so a second
debit would replay the first, never charge again.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
from app.core.enums import LedgerReason
from app.core.errors import AppError
from app.core.pagination import Cursor, PageParams
from app.core.queue import Queue
from app.core.security import likes_handle_key
from app.core.storage_keys import public_url
from app.modules.discovery import repository as discovery_repository
from app.modules.discovery import service as discovery_service
from app.modules.discovery.schemas import PublicProfile
from app.modules.likes import repository, rules
from app.modules.likes.schemas import LikeCard, LikeCardPage, LikesCount
from app.modules.photos import service as photos_service
from app.modules.pricing import service as pricing_service
from app.modules.users.models import User
from app.modules.wallet.rules import Ref, RefType

# `(liked_at, handle)`: the last like's place, newest first. Never the liker's
# id, which the handle exists to keep from a man who hasn't paid.
LIKES_CURSOR = Cursor(tuple[AwareDatetime, str])


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Not found.", status=404)


async def likes(
    session: AsyncSession,
    user: User,
    *,
    params: PageParams,
    settings: Settings,
    queue: Queue,
) -> LikeCardPage:
    after = None if params.cursor is None else LIKES_CURSOR.decode(params.cursor)
    key = likes_handle_key(settings)
    everyone = rules.sees_everyone(user.gender)
    async with session.begin():
        viewer = await discovery_service.viewer_of(session, user)
        rows = await repository.likes(
            session, viewer, key, after=after, limit=params.fetch
        )
        shown = [row.liker_id for row in rows if everyone or row.revealed]
        hidden = [row.liker_id for row in rows if not (everyone or row.revealed)]
        details = await discovery_repository.cards(session, shown)
        metres = await repository.distances(session, user.id, shown)
        photos = await repository.main_photos(session, hidden)
    now = clock.now()
    to_blur = [photo_id for photo_id, blur in photos.values() if blur is None]
    for photo_id in to_blur:
        # Approved before T-6.7 made blurs: made now, shown on a later look.
        await photos_service.queue_blur(queue, photo_id)
    items: list[LikeCard] = []
    liked_at: dict[str, datetime] = {}
    for row in rows:
        liked_at[row.handle] = row.liked_at
        if row.liker_id in details:
            card = discovery_service.card_of(
                details[row.liker_id], metres.get(row.liker_id), now, settings
            )
            items.append(
                LikeCard(
                    handle=row.handle,
                    is_super=row.is_super,
                    card=card,
                    blurred_photo_url=None,
                )
            )
        else:
            blur = photos.get(row.liker_id, (None, None))[1]
            items.append(
                LikeCard(
                    handle=row.handle,
                    is_super=row.is_super,
                    card=None,
                    blurred_photo_url=None
                    if blur is None
                    else public_url(settings, blur),
                )
            )
    return LikeCardPage.of(
        items,
        params,
        lambda item: LIKES_CURSOR.encode((liked_at[item.handle], item.handle)),
    )


async def count(session: AsyncSession, user: User, *, settings: Settings) -> LikesCount:
    async with session.begin():
        viewer = await discovery_service.viewer_of(session, user)
        found = await repository.count(session, viewer, likes_handle_key(settings))
    return LikesCount(count=found)


async def reveal(
    session: AsyncSession,
    user: User,
    handle: str,
    *,
    shown_price: int,
    settings: Settings,
) -> PublicProfile:
    """The profile behind `handle`, paid for once (D-542), at the price the
    screen showed, or `PRICE_CHANGED` with nothing charged or written (P-56).
    Revealed before, or a woman's: the profile, and nothing charged. Not a
    like still waiting on this viewer: `NOT_FOUND`, as for a handle nobody
    holds."""
    if not rules.is_handle(handle):
        raise _not_found()
    async with session.begin():
        viewer = await discovery_service.viewer_of(session, user)
        liker_id: UUID | None = await repository.liker_by_handle(
            session, viewer, likes_handle_key(settings), handle
        )
        if liker_id is None:
            raise _not_found()
        if await repository.record_reveal(session, user.id, liker_id):
            await pricing_service.charge(
                session,
                user,
                LedgerReason.LIKED_YOU_REVEAL,
                shown=shown_price,
                ref=Ref(RefType.USER, liker_id),
            )
        return await discovery_service.public_profile_in(
            session, user, liker_id, settings=settings
        )
