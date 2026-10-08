"""Discovery (T-6.2): the ranked feed of people nearby; and (T-6.3) one
person's public profile.

Who may be seen is `repository.visible_to`, one rule the feed, the public
profile (T-6.3) and swipes (T-6.4) share. The feed adds the radius from
`app_config` and leaves out anyone the viewer already swiped. Everything is
measured between grid points (D-490), at the scroll's `as_of` (D-491).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
from app.core.enums import FraudBand
from app.core.enums import Kudos as KudosKind
from app.core.errors import AppError, invalid_field
from app.core.pagination import Cursor, PageParams
from app.core.storage_keys import public_url
from app.modules.admin import service as admin_service
from app.modules.discovery import repository, rules
from app.modules.discovery.schemas import (
    Card,
    CardPage,
    Feed,
    KudosCounts,
    PublicProfile,
    ThreadWithMe,
)
from app.modules.profiles import repository as profiles_repository
from app.modules.users import service as users_service
from app.modules.users.models import User

# `(as_of, score, user_id)`: the instant the scroll was ranked at, then the last
# card's place in it (D-491). A position, never a permission (D-270).
FEED_CURSOR = Cursor(tuple[AwareDatetime, float, UUID])

RADIUS_KEY = "discovery_radius_km"


async def viewer_of(session: AsyncSession, user: User) -> repository.Viewer:
    """The viewer as the rules read them, in the caller's transaction."""
    band = await repository.band_of(session, user.id)
    return repository.Viewer(
        id=user.id,
        gender=user.gender,
        seeking=await repository.seeking_of(session, user.id),
        shadowed=band is FraudBand.SHADOW,
        position=await repository.position_of(session, user.id),
    )


async def discover(
    session: AsyncSession,
    user: User,
    *,
    feed: Feed,
    intent_ids: Collection[int],
    verified: bool,
    params: PageParams,
    settings: Settings,
) -> CardPage:
    """One page of `feed` for `user`. `intent_ids` keeps those sharing any of
    them (D-041); `verified`, those showing the badge (D-393)."""
    as_of, after = clock.now(), None
    if params.cursor is not None:
        as_of, score, last = FEED_CURSOR.decode(params.cursor)
        after = (score, last)
    async with session.begin():
        await _refuse_unknown_intents(session, intent_ids)
        viewer = await viewer_of(session, user)
        radius_km = await admin_service.config_int(session, RADIUS_KEY)
        if viewer.position is None:
            # Finishing needs a location (D-310), so only an account changed
            # by hand has none: nobody is near nowhere.
            return CardPage(items=[], next_cursor=None)
        rows = await repository.feed(
            session,
            viewer,
            as_of=as_of,
            radius_m=radius_km * 1000.0,
            new_first=feed is Feed.NEW,
            online_since=as_of - rules.ONLINE_FOR if feed is Feed.ONLINE else None,
            intent_ids=intent_ids,
            badge_only=verified,
            after=after,
            limit=params.fetch,
        )
        details = await repository.cards(session, [row.user_id for row in rows])
    now = clock.now()
    cards = [
        card_of(details[row.user_id], row.distance_m, now, settings) for row in rows
    ]
    scores = {row.user_id: row.score for row in rows}
    return CardPage.of(
        cards,
        params,
        lambda card: FEED_CURSOR.encode((as_of, scores[card.id], card.id)),
    )


async def _refuse_unknown_intents(
    session: AsyncSession, intent_ids: Collection[int]
) -> None:
    known = await profiles_repository.known_intent_ids(session, intent_ids)
    if set(intent_ids) - known:
        raise invalid_field("intent_ids", "names an intent that doesn't exist")


def card_of(
    row: Row[Any], distance_m: float | None, now: datetime, settings: Settings
) -> Card:
    """A `Card` from `repository.cards`' row: the age and distance unless
    hidden, the main photo's URL, and the badge as the query computed it."""
    hide_distance = row.hide_distance or distance_m is None
    return Card(
        id=row.id,
        first_name=row.first_name,
        age=None
        if row.hide_age or row.dob is None
        else users_service.age_on(row.dob, clock.today_ist()),
        username=row.username,
        city=row.city,
        hometown=row.hometown,
        distance_km=None if hide_distance else rules.distance_km(distance_m or 0.0),
        intent_ids=sorted(row.intent_ids or []),
        bio_line=rules.bio_line(row.about),
        main_photo_url=None
        if row.main_photo_key is None
        else public_url(settings, row.main_photo_key),
        shows_badge=bool(row.shows_badge),
        is_online=row.last_active_at is not None
        and row.last_active_at >= now - rules.ONLINE_FOR,
        is_new=row.created_at >= now - rules.NEW_FOR,
    )


# --- The public profile (T-6.3) ------------------------------------------------------


def _not_found() -> AppError:
    """One answer for nobody, someone blocked either way, hidden, not done,
    not active or held back by their band: which, the asker never learns
    (04-API: `NOT_FOUND` for a blocked user too)."""
    return AppError("NOT_FOUND", "Not found.", status=404)


async def public_profile(
    session: AsyncSession, user: User, user_id: UUID, *, settings: Settings
) -> PublicProfile:
    """`user_id`'s profile as `user` may see it (D-493), and the view
    recorded; your own needs no permission and records nothing."""
    own = user_id == user.id
    async with session.begin():
        viewer = await viewer_of(session, user)
        if not own and not await repository.is_visible(session, viewer, user_id):
            raise _not_found()
        rows = await repository.cards(session, [user_id])
        row = rows.get(user_id)
        if row is None:
            raise _not_found()
        distance = (
            None
            if own
            else await repository.distance_between(session, user.id, user_id)
        )
        keys = await repository.public_photo_keys(session, user_id)
        interests = await repository.interest_ids(session, user_id)
        kudos = (
            await repository.kudos_counts(session, user_id) if row.show_kudos else None
        )
        album = await repository.album_photo_count(session, user_id)
        match_id = (
            None if own else await repository.match_between(session, user.id, user_id)
        )
        thread = (
            None if own else await repository.thread_between(session, user.id, user_id)
        )
        if not own:
            await repository.record_view(session, user.id, user_id, clock.now())
    card = card_of(row, distance, clock.now(), settings)
    return PublicProfile(
        **card.model_dump(),
        about=row.about or "",
        photo_urls=[public_url(settings, key) for key in keys],
        interest_ids=interests,
        kudos=None
        if kudos is None
        else KudosCounts(**{kind.value: kudos.get(kind, 0) for kind in KudosKind}),
        album_photo_count=album,
        match_id=match_id,
        thread=None
        if thread is None
        else ThreadWithMe(
            id=thread.id, status=thread.status, expires_at=thread.expires_at
        ),
    )
