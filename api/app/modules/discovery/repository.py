"""SQL for discovery (T-6.2): who a viewer may see, the ranked feed, and what
each card needs. No rules here: `rules.py` says what each condition is, the
service decides which apply.

02-ARCHITECTURE §8 is the query this builds. The feed reads only grid points
(D-490), so the radius, the distance and the ranking all are measured between
them. The ranking is computed once per candidate in an inner query; the outer
one pages it by `(score, user_id)`, the cursor's key, and the page's photo,
badge and intents are read for its rows alone.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    ColumnElement,
    Float,
    Row,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.enums import (
    FraudBand,
    Gender,
    OnboardingStep,
    PhotoKind,
    ReviewStatus,
    Seeking,
    UserStatus,
)
from app.modules.discovery import rules
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile, ProfileIntent
from app.modules.safety.models import Block, FraudScore
from app.modules.swipes.models import Swipe
from app.modules.users.models import User
from app.modules.verification.repository import badge_of


@dataclass(frozen=True)
class Viewer:
    """Who is looking, as the rules read them."""

    id: UUID
    gender: Gender | None
    seeking: Seeking | None
    # In D-031's `shadow` band: then shadowed profiles are shown to them.
    shadowed: bool
    # Their grid point (D-490), (lat, lng); None before they set one.
    position: tuple[float, float] | None = None


async def band_of(session: AsyncSession, user_id: UUID) -> FraudBand:
    """D-031's band; `normal` for someone never scored."""
    band = await session.scalar(
        select(FraudScore.band).where(FraudScore.user_id == user_id)
    )
    return band if band is not None else FraudBand.NORMAL


async def seeking_of(session: AsyncSession, user_id: UUID) -> Seeking | None:
    seeking: Seeking | None = await session.scalar(
        select(Profile.seeking).where(Profile.user_id == user_id)
    )
    return seeking


async def position_of(
    session: AsyncSession, user_id: UUID
) -> tuple[float, float] | None:
    """The user's stored grid point as (lat, lng), or None."""
    row = (
        await session.execute(
            select(
                func.ST_Y(cast(Profile.location, Geometry)),
                func.ST_X(cast(Profile.location, Geometry)),
            ).where(Profile.user_id == user_id, Profile.location.is_not(None))
        )
    ).first()
    return None if row is None else (float(row[0]), float(row[1]))


def _point_written_in(position: tuple[float, float]) -> Any:
    """The viewer's grid point, written into the statement as constants, never
    as parameters or a subquery: Postgres then plans for how many people really
    are within the radius there. Behind a parameter it guesses a handful, and on
    a crowded launch city (everyone inside 25 km) picks per-row loops that cost
    several times the scan. Safe to write in: two floats the database itself
    stored, never the client's text."""
    lat, lng = position
    return cast(
        func.ST_SetSRID(
            func.ST_MakePoint(
                literal(float(lng), Float, literal_execute=True),
                literal(float(lat), Float, literal_execute=True),
            ),
            4326,
        ),
        Geography(geometry_type="POINT", srid=4326),
    )


def _in_band(user_id: Any, band: FraudBand) -> ColumnElement[bool]:
    return exists().where(FraudScore.user_id == user_id, FraudScore.band == band)


def blocked_either_way(a: Any, b: Any) -> ColumnElement[bool]:
    """A block between `a` and `b`, whoever made it (06-TESTING's critical 9)."""
    return exists().where(
        or_(
            and_(Block.blocker_id == a, Block.blocked_id == b),
            and_(Block.blocker_id == b, Block.blocked_id == a),
        )
    )


def visible_to(
    viewer: Viewer,
    *,
    mutual: bool,
    hidden_ok: ColumnElement[bool] | None = None,
) -> list[ColumnElement[bool]]:
    """The conditions on `users` and `profiles` (joined by the caller) under
    which that person may be shown to `viewer`: not themselves, active, done,
    not hidden (unless `hidden_ok` says so, T-6.3's exception), not frozen
    (D-031), shadowed only to the shadowed, and no block either way. With
    `mutual`, also each one wanting the other's gender (the feed, and swipes).
    Never the radius nor swiped: those are the feed's own."""
    hidden = Profile.is_hidden.is_(False)
    conditions = [
        User.id != viewer.id,
        User.status == UserStatus.ACTIVE,
        User.onboarding_step == OnboardingStep.DONE,
        hidden if hidden_ok is None else or_(hidden, hidden_ok),
        ~_in_band(User.id, FraudBand.FREEZE),
        ~blocked_either_way(viewer.id, User.id),
    ]
    if not viewer.shadowed:
        conditions.append(~_in_band(User.id, FraudBand.SHADOW))
    if mutual:
        conditions += [
            User.gender.in_(rules.wanted_genders(viewer.seeking)),
            Profile.seeking.in_(rules.seekings_wanting(viewer.gender)),
        ]
    return conditions


def _seconds(interval: Any) -> Any:
    return cast(func.extract("epoch", interval), Float)


def _score(distance_m: Any, as_of: datetime, *, new_first: bool) -> Any:
    """D-491's score, at `as_of`, in float8 throughout so a cursor's score
    compares exactly with the same row's score recomputed."""
    distance = 1.0 / (1.0 + distance_m / (rules.DISTANCE_HALF_KM * 1000.0))
    recency = case(
        (User.last_active_at.is_(None), 0.0),
        else_=1.0
        / (
            1.0
            + func.greatest(0.0, _seconds(literal(as_of) - User.last_active_at))
            / rules.RECENCY_HALF.total_seconds()
        ),
    )
    verified = case((User.is_verified.is_(True), 1.0), else_=0.0)
    completeness = cast(Profile.completeness, Float) / 100.0
    score = (
        rules.WEIGHT_DISTANCE * distance
        + rules.WEIGHT_RECENCY * recency
        + rules.WEIGHT_VERIFIED * verified
        + rules.WEIGHT_COMPLETENESS * completeness
    )
    if new_first:
        score = score + case(
            (User.created_at >= literal(as_of - rules.NEW_FOR), rules.NEW_LIFT),
            else_=0.0,
        )
    return cast(score, Float)


def feed_query(
    viewer: Viewer,
    *,
    as_of: datetime,
    radius_m: float,
    new_first: bool,
    online_since: datetime | None,
    intent_ids: Collection[int],
    badge_only: bool,
    after: tuple[float, UUID] | None,
    limit: int,
) -> Select[tuple[UUID, float, float]]:
    """One page of the viewer's feed: `(user_id, score, distance_m)`, best
    first, then by id; after `after`, a `(score, user_id)` this feed wrote.
    The statement itself, so the plan test and the bench read exactly what
    the API runs (T-6.2). Every candidate is scored: in one city crowded far
    past beta scale that is the request's cost (D-495, P-391)."""
    if viewer.position is None:
        raise ValueError("a feed needs the viewer's position; the service checks first")
    here = _point_written_in(viewer.position)
    distance = func.ST_Distance(Profile.location, here)
    conditions = [
        *visible_to(viewer, mutual=True),
        func.ST_DWithin(Profile.location, here, radius_m),
        ~exists().where(Swipe.swiper_id == viewer.id, Swipe.target_id == User.id),
    ]
    if online_since is not None:
        conditions.append(User.last_active_at >= online_since)
    if intent_ids:
        conditions.append(
            exists().where(
                ProfileIntent.user_id == User.id,
                ProfileIntent.intent_id.in_(list(intent_ids)),
            )
        )
    if badge_only:
        conditions.append(badge_of(User.id, User.is_verified))
    ranked = (
        select(
            User.id.label("user_id"),
            _score(distance, as_of, new_first=new_first).label("score"),
            cast(distance, Float).label("distance_m"),
        )
        .select_from(User)
        .join(Profile, Profile.user_id == User.id)
        .where(*conditions)
        .subquery("ranked")
    )
    query = select(ranked.c.user_id, ranked.c.score, ranked.c.distance_m)
    if after is not None:
        score, user_id = after
        query = query.where(
            or_(
                ranked.c.score < score,
                and_(ranked.c.score == score, ranked.c.user_id > user_id),
            )
        )
    return query.order_by(ranked.c.score.desc(), ranked.c.user_id).limit(limit)


# Postgres's JIT compiles this statement on every request, its cost being
# high, and the compiling took longer than the query (T-6.2's bench: 399 to
# 575 ms with it, 112 without). Off for the feed's own transaction only, never
# for the database (D-495).
JIT_OFF = text("SET LOCAL jit = off")


async def feed(
    session: AsyncSession, viewer: Viewer, **page: Any
) -> Sequence[Row[tuple[UUID, float, float]]]:
    """`feed_query`'s rows, with JIT off for the caller's transaction."""
    await session.execute(JIT_OFF)
    return (await session.execute(feed_query(viewer, **page))).all()


def main_photo_key(user_id: Any) -> Any:
    """The public key of the profile's main photo: its approved public photo
    at the lowest place (P-75, D-494). The server never closes a gap, so the
    lowest is the main one whether or not it is 0; none, no row."""
    return (
        select(Photo.public_key)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.PUBLIC,
            Photo.status == ReviewStatus.APPROVED,
            Photo.public_key.is_not(None),
        )
        .order_by(Photo.position, Photo.id)
        .limit(1)
        .scalar_subquery()
    )


def _intent_ids(user_id: Any) -> Any:
    return (
        select(func.array_agg(ProfileIntent.intent_id))
        .where(ProfileIntent.user_id == user_id)
        .scalar_subquery()
    )


async def cards(
    session: AsyncSession, user_ids: Sequence[UUID]
) -> dict[UUID, Row[Any]]:
    """What each of these people's `Card` says, by id."""
    if not user_ids:
        return {}
    rows = await session.execute(
        select(
            User.id,
            User.dob,
            User.created_at,
            User.last_active_at,
            Profile.first_name,
            Profile.username,
            Profile.city,
            Profile.hometown,
            Profile.about,
            Profile.hide_age,
            Profile.hide_distance,
            main_photo_key(User.id).label("main_photo_key"),
            badge_of(User.id, User.is_verified).label("shows_badge"),
            _intent_ids(User.id).label("intent_ids"),
        )
        .join(Profile, Profile.user_id == User.id)
        .where(User.id.in_(list(user_ids)))
    )
    return {row.id: row for row in rows}
