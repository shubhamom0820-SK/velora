"""SQL for liked you (T-6.7). No rules here: the service decides.

Who is listed is one query, `_likers`: someone's like or Super Like of the
viewer that the viewer hasn't answered with a swipe, from someone discovery's
`visible_to` lets the viewer see, mutually, as a swipe back needs (D-492).
The list, its count and a reveal's lookup all read it, so they can't
disagree about who is there.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Float,
    LargeBinary,
    Row,
    Text,
    and_,
    bindparam,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.core.enums import PhotoKind, ReviewStatus
from app.modules.discovery.repository import Viewer, visible_to
from app.modules.likes import rules
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from app.modules.swipes.models import LikedYouReveal, Swipe
from app.modules.users.models import User


def handle_of(viewer_id: UUID, liker: Any, key: bytes) -> Any:
    """`rules`' handle, computed by the database: hex of the first 16 bytes of
    HMAC-SHA256(key, "<viewer id>:<liker id>")."""
    message = func.convert_to(
        literal(str(viewer_id), Text) + ":" + cast(liker, Text), "UTF8"
    )
    digest = func.hmac(
        message, bindparam("handle_key", key, type_=LargeBinary), "sha256"
    )
    return func.encode(func.substring(digest, 1, rules.HANDLE_HEX // 2), "hex")


def _likers(viewer: Viewer, key: bytes) -> Select[Any]:
    """Every like of the viewer still waiting on them: `(liker_id, is_super,
    liked_at, handle, revealed)`, before any order."""
    mine = aliased(Swipe)
    return (
        select(
            Swipe.swiper_id.label("liker_id"),
            (Swipe.dir == "super").label("is_super"),
            Swipe.created_at.label("liked_at"),
            handle_of(viewer.id, Swipe.swiper_id, key).label("handle"),
            exists()
            .where(
                LikedYouReveal.viewer_id == viewer.id,
                LikedYouReveal.liker_id == Swipe.swiper_id,
            )
            .label("revealed"),
        )
        .select_from(Swipe)
        .join(User, User.id == Swipe.swiper_id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            Swipe.target_id == viewer.id,
            Swipe.dir.in_(list(rules.LIKES)),
            ~exists().where(
                mine.swiper_id == viewer.id, mine.target_id == Swipe.swiper_id
            ),
            *visible_to(viewer, mutual=True),
        )
    )


async def likes(
    session: AsyncSession,
    viewer: Viewer,
    key: bytes,
    *,
    after: tuple[datetime, str] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """One page of `_likers`, newest first, then by handle; after `after`, a
    `(liked_at, handle)` this list wrote."""
    listed = _likers(viewer, key).subquery("listed")
    query = select(listed)
    if after is not None:
        liked_at, handle = after
        query = query.where(
            or_(
                listed.c.liked_at < liked_at,
                and_(listed.c.liked_at == liked_at, listed.c.handle > handle),
            )
        )
    query = query.order_by(listed.c.liked_at.desc(), listed.c.handle).limit(limit)
    return (await session.execute(query)).all()


async def count(session: AsyncSession, viewer: Viewer, key: bytes) -> int:
    found = await session.scalar(
        select(func.count()).select_from(_likers(viewer, key).subquery())
    )
    return found or 0


async def liker_by_handle(
    session: AsyncSession, viewer: Viewer, key: bytes, handle: str
) -> UUID | None:
    """Whose like of the viewer `handle` names, if it is still listed."""
    listed = _likers(viewer, key).subquery("listed")
    found: UUID | None = await session.scalar(
        select(listed.c.liker_id).where(listed.c.handle == handle)
    )
    return found


async def record_reveal(session: AsyncSession, viewer_id: UUID, liker_id: UUID) -> bool:
    """Write the reveal, once: True if this call wrote it. A second at once
    waits on the first's row and writes nothing, so only one pays."""
    written = await session.scalar(
        insert(LikedYouReveal)
        .values(viewer_id=viewer_id, liker_id=liker_id)
        .on_conflict_do_nothing(index_elements=["viewer_id", "liker_id"])
        .returning(LikedYouReveal.liker_id)
    )
    return written is not None


async def distances(
    session: AsyncSession, viewer_id: UUID, user_ids: Sequence[UUID]
) -> dict[UUID, float | None]:
    """Metres between the viewer's grid point and each of these people's
    (D-490); None where either has none."""
    if not user_ids:
        return {}
    mine = (
        select(Profile.location).where(Profile.user_id == viewer_id).scalar_subquery()
    )
    rows = await session.execute(
        select(
            Profile.user_id, cast(func.ST_Distance(Profile.location, mine), Float)
        ).where(Profile.user_id.in_(list(user_ids)))
    )
    return {user_id: metres for user_id, metres in rows.tuples()}


async def main_photos(
    session: AsyncSession, user_ids: Sequence[UUID]
) -> dict[UUID, tuple[UUID, str | None]]:
    """Each person's main photo, as the `Card`'s (D-494): the approved public
    photo at the lowest place, by its id and its blurred copy's key; nobody
    without a photo is in it."""
    if not user_ids:
        return {}
    rows = await session.execute(
        select(Photo.user_id, Photo.id, Photo.blur_key)
        .distinct(Photo.user_id)
        .where(
            Photo.user_id.in_(list(user_ids)),
            Photo.kind == PhotoKind.PUBLIC,
            Photo.status == ReviewStatus.APPROVED,
            Photo.public_key.is_not(None),
        )
        .order_by(Photo.user_id, Photo.position, Photo.id)
    )
    return {user_id: (photo_id, blur) for user_id, photo_id, blur in rows.tuples()}
