"""SQL for discovery (T-6.2): who a viewer may see, the ranked feed, what each
card needs, the public profile (T-6.3) and search (T-6.6). No rules here:
`rules.py` says what each condition is, the service decides which apply.

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
    Text,
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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
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
from app.core.enums import Kudos as KudosKind
from app.modules.discovery import rules
from app.modules.discovery.models import ProfileView
from app.modules.kudos.models import Kudos as KudosGiven
from app.modules.matches.models import Match
from app.modules.photos.models import Photo
from app.modules.profiles.models import (
    Intent,
    Interest,
    Profile,
    ProfileIntent,
    ProfileInterest,
)
from app.modules.safety.models import Block, FraudScore
from app.modules.swipes.models import Swipe
from app.modules.threads.models import Thread
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


def _shown_photo(user_id: Any) -> list[ColumnElement[bool]]:
    """A photo anyone may see: the user's public photo, approved, with its
    public copy. The card's main photo and the profile's list both read it."""
    return [
        Photo.user_id == user_id,
        Photo.kind == PhotoKind.PUBLIC,
        Photo.status == ReviewStatus.APPROVED,
        Photo.public_key.is_not(None),
    ]


def main_photo_key(user_id: Any) -> Any:
    """The public key of the profile's main photo: its approved public photo
    at the lowest place (P-75, D-494). The server never closes a gap, so the
    lowest is the main one whether or not it is 0; none, no row."""
    return (
        select(Photo.public_key)
        .where(*_shown_photo(user_id))
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
            Profile.show_kudos,
            main_photo_key(User.id).label("main_photo_key"),
            badge_of(User.id, User.is_verified).label("shows_badge"),
            _intent_ids(User.id).label("intent_ids"),
        )
        .join(Profile, Profile.user_id == User.id)
        .where(User.id.in_(list(user_ids)))
    )
    return {row.id: row for row in rows}


# --- The public profile (T-6.3) ------------------------------------------------------


def _as_uuid(value: Any) -> Any:
    """An id bound as `uuid`. `least()` and `greatest()` give a bare value no
    type, and asyncpg's own UUID, which an id read back from a query is, binds
    as nothing at all, so Postgres takes it for text (found by T-6.6's lookup
    by username). A column keeps its own type."""
    if isinstance(value, UUID):
        return literal(value, PG_UUID(as_uuid=True))
    return value


def _pair_low(a: Any, b: Any) -> Any:
    return func.least(_as_uuid(a), _as_uuid(b))


def _pair_high(a: Any, b: Any) -> Any:
    return func.greatest(_as_uuid(a), _as_uuid(b))


def shares_a_match_or_thread(viewer_id: UUID, other: Any) -> ColumnElement[bool]:
    """A match or a Thread between the viewer and `other`, either kind: what
    lets the viewer still open a hidden profile (D-493)."""
    low, high = _pair_low(viewer_id, other), _pair_high(viewer_id, other)
    return or_(
        exists().where(Match.user_low == low, Match.user_high == high),
        exists().where(Thread.user_low == low, Thread.user_high == high),
    )


async def is_visible(
    session: AsyncSession, viewer: Viewer, user_id: UUID, *, mutual: bool = False
) -> bool:
    """Whether `viewer` may open `user_id`'s profile (D-493): `visible_to`
    without seeking or the radius, which a link reaches past, and a hidden
    profile only to someone it shares a match or a Thread with. With `mutual`,
    each must want the other's gender too: a private message (T-7.1, D-550)."""
    found = await session.scalar(
        select(User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.id == user_id,
            *visible_to(
                viewer,
                mutual=mutual,
                hidden_ok=shares_a_match_or_thread(viewer.id, User.id),
            ),
        )
    )
    return found is not None


async def distance_between(session: AsyncSession, a: UUID, b: UUID) -> float | None:
    """Metres between two people's grid points (D-490); None if either has none."""
    other = aliased(Profile)
    metres = await session.scalar(
        select(func.ST_Distance(Profile.location, other.location))
        .select_from(Profile)
        .join(other, other.user_id == b)
        .where(Profile.user_id == a)
    )
    return None if metres is None else float(metres)


async def public_photo_keys(session: AsyncSession, user_id: UUID) -> list[str]:
    """Every approved public photo's public key, in place order: the first is
    the main one (P-75)."""
    keys = await session.scalars(
        select(Photo.public_key)
        .where(*_shown_photo(user_id))
        .order_by(Photo.position, Photo.id)
    )
    return [key for key in keys if key is not None]


async def interest_ids(session: AsyncSession, user_id: UUID) -> list[int]:
    ids = await session.scalars(
        select(ProfileInterest.interest_id)
        .where(ProfileInterest.user_id == user_id)
        .order_by(ProfileInterest.interest_id)
    )
    return list(ids)


async def kudos_counts(session: AsyncSession, user_id: UUID) -> dict[KudosKind, int]:
    rows = await session.execute(
        select(KudosGiven.kind, func.count())
        .where(KudosGiven.to_id == user_id)
        .group_by(KudosGiven.kind)
    )
    return {kind: count for kind, count in rows.tuples()}


async def album_photo_count(session: AsyncSession, user_id: UUID) -> int:
    """Their approved private photos the album shows, those with a scored copy
    (D-700, T-8.4): a number, never one of them. One approved before D-700 has
    none, so it is neither shown nor counted."""
    count = await session.scalar(
        select(func.count())
        .select_from(Photo)
        .where(
            Photo.user_id == user_id,
            Photo.kind == PhotoKind.PRIVATE,
            Photo.status == ReviewStatus.APPROVED,
            Photo.scored_key.is_not(None),
        )
    )
    return count or 0


async def match_between(session: AsyncSession, a: UUID, b: UUID) -> UUID | None:
    found: UUID | None = await session.scalar(
        select(Match.id).where(
            Match.user_low == _pair_low(a, b), Match.user_high == _pair_high(a, b)
        )
    )
    return found


async def thread_between(session: AsyncSession, a: UUID, b: UUID) -> Thread | None:
    found: Thread | None = await session.scalar(
        select(Thread).where(
            Thread.user_low == _pair_low(a, b), Thread.user_high == _pair_high(a, b)
        )
    )
    return found


async def record_view(
    session: AsyncSession, viewer_id: UUID, viewed_id: UUID, at: datetime
) -> None:
    """One row per viewer and profile: the first view writes it, each later
    one moves its time and counts it (for "viewed you", backlog B-5)."""
    statement = insert(ProfileView).values(
        viewer_id=viewer_id, viewed_id=viewed_id, last_viewed_at=at
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[ProfileView.viewer_id, ProfileView.viewed_id],
            set_={
                "last_viewed_at": statement.excluded.last_viewed_at,
                "view_count": ProfileView.view_count + 1,
            },
        )
    )


# --- Search (T-6.6) ---------------------------------------------------------------


async def user_id_by_username(session: AsyncSession, username: str) -> UUID | None:
    """Whose username this is, in any case (`citext`), or None. Who may see
    them is the caller's question."""
    found: UUID | None = await session.scalar(
        select(Profile.user_id).where(Profile.username == username)
    )
    return found


async def catalogue_matching(
    session: AsyncSession, term: str
) -> tuple[list[int], list[int]]:
    """The intents and the interests whose label holds `term`, in any case:
    two catalogues of a few dozen rows (D-041, T-3.8)."""
    pattern = rules.like_contains(term)
    intents = await session.scalars(
        select(Intent.id).where(Intent.label.ilike(pattern, escape="\\"))
    )
    interests = await session.scalars(
        select(Interest.id).where(Interest.label.ilike(pattern, escape="\\"))
    )
    return list(intents), list(interests)


def _username_text() -> Any:
    """The username as text in byte order, so the order, the cursor's
    comparison and Python's agree whatever the database's collation."""
    return cast(Profile.username, Text).collate("C")


def username_search_query(
    viewer: Viewer, term: str, *, after: tuple[bool, str] | None, limit: int
) -> Select[tuple[UUID, bool]]:
    """`@` search (D-540): usernames starting with `term`, the exact one first,
    then in order. Anyone `visible_to` allows without seeking or the radius,
    as a link (D-493), and never a hidden profile, whatever is shared with it:
    hidden stays out of search."""
    username = _username_text()
    ranked = (
        select(
            User.id.label("user_id"),
            (Profile.username == term).label("exact"),
            username.label("username"),
        )
        .select_from(User)
        .join(Profile, Profile.user_id == User.id)
        .where(
            *visible_to(viewer, mutual=False),
            Profile.username.ilike(rules.like_prefix(term), escape="\\"),
        )
        .subquery("ranked")
    )
    query = select(ranked.c.user_id, ranked.c.exact)
    if after is not None:
        was_exact, last = after
        later = and_(ranked.c.exact.is_(was_exact), ranked.c.username > last)
        query = query.where(
            or_(ranked.c.exact.is_(False), later) if was_exact else later
        )
    return query.order_by(ranked.c.exact.desc(), ranked.c.username).limit(limit)


def text_search_query(
    viewer: Viewer,
    term: str,
    *,
    radius_m: float,
    intent_ids: Collection[int],
    interest_ids: Collection[int],
    after: tuple[float, UUID] | None,
    limit: int,
) -> Select[tuple[UUID, float]]:
    """Text search (D-540): within the radius, whom the feed could show,
    swiped or not; matched by name or username (a trigram match or a prefix),
    a city starting with `term`, or an intent or interest whose label holds
    it. Best name match first, then by id."""
    if viewer.position is None:
        raise ValueError("text search needs the viewer's position; the service checks")
    here = _point_written_in(viewer.position)
    username = cast(Profile.username, Text)
    prefix = rules.like_prefix(term)
    matches: list[ColumnElement[bool]] = [
        Profile.first_name.op("%")(term),
        username.op("%")(term),
        Profile.first_name.ilike(prefix, escape="\\"),
        Profile.username.ilike(prefix, escape="\\"),
        Profile.city.ilike(prefix, escape="\\"),
    ]
    if intent_ids:
        matches.append(
            exists().where(
                ProfileIntent.user_id == User.id,
                ProfileIntent.intent_id.in_(list(intent_ids)),
            )
        )
    if interest_ids:
        matches.append(
            exists().where(
                ProfileInterest.user_id == User.id,
                ProfileInterest.interest_id.in_(list(interest_ids)),
            )
        )
    score = cast(
        func.greatest(
            func.similarity(Profile.first_name, term), func.similarity(username, term)
        ),
        Float,
    )
    ranked = (
        select(User.id.label("user_id"), score.label("score"))
        .select_from(User)
        .join(Profile, Profile.user_id == User.id)
        .where(
            *visible_to(viewer, mutual=True),
            func.ST_DWithin(Profile.location, here, radius_m),
            or_(*matches),
        )
        .subquery("ranked")
    )
    query = select(ranked.c.user_id, ranked.c.score)
    if after is not None:
        last_score, last_id = after
        query = query.where(
            or_(
                ranked.c.score < last_score,
                and_(ranked.c.score == last_score, ranked.c.user_id > last_id),
            )
        )
    return query.order_by(ranked.c.score.desc(), ranked.c.user_id).limit(limit)


# pg_trgm's `%` threshold for the search's own transaction, never left to the
# database's setting (D-540).
SIMILARITY = text(f"SET LOCAL pg_trgm.similarity_threshold = {rules.SIMILARITY}")


async def username_search(
    session: AsyncSession, viewer: Viewer, term: str, **page: Any
) -> Sequence[Row[tuple[UUID, bool]]]:
    return (await session.execute(username_search_query(viewer, term, **page))).all()


async def text_search(
    session: AsyncSession, viewer: Viewer, term: str, **page: Any
) -> Sequence[Row[tuple[UUID, float]]]:
    await session.execute(SIMILARITY)
    return (await session.execute(text_search_query(viewer, term, **page))).all()


# --- The public link (T-6.8) --------------------------------------------------------


async def shared(session: AsyncSession, username: str) -> Row[Any] | None:
    """The profile `/@username` shows someone not signed in, in any case, or
    None (D-544): its owner turned the public link on, and it is active, done,
    not hidden, and in neither the `freeze` nor the `shadow` band. No viewer,
    so no block: anyone on the internet may ask."""
    return (
        await session.execute(
            select(
                User.dob,
                Profile.username,
                Profile.first_name,
                Profile.city,
                Profile.hide_age,
                main_photo_key(User.id).label("main_photo_key"),
            )
            .join(Profile, Profile.user_id == User.id)
            .where(
                Profile.username == username,
                Profile.public_link.is_(True),
                Profile.is_hidden.is_(False),
                User.status == UserStatus.ACTIVE,
                User.onboarding_step == OnboardingStep.DONE,
                ~_in_band(User.id, FraudBand.FREEZE),
                ~_in_band(User.id, FraudBand.SHADOW),
            )
        )
    ).first()
