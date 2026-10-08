"""SQL for the private album (T-8.4). No rules here: the service decides."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, delete, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import AlbumRequestStatus, PhotoKind, ReviewStatus
from app.modules.album.models import AlbumCopy, AlbumRequest
from app.modules.discovery.repository import blocked_either_way, main_photo_key
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.modules.verification.repository import badge_of

# The advisory lock's first key, meaning "a requester's album requests"; the
# second is the requester's hash. Gifts' senders lock on 89, Swipes' pairs on
# 64, Threads' on 71, P-55's slots on 55.
REQUESTER_LOCK = 97

LIVE = (AlbumRequestStatus.PENDING, AlbumRequestStatus.GRANTED)
CLOSED = (AlbumRequestStatus.DECLINED, AlbumRequestStatus.REVOKED)


def _albumable(owner_id: Any) -> tuple[Any, ...]:
    """A photo the album shows: the owner's approved private photo with a
    scored copy, the bytes moderation scored (P-79, D-700). One approved before
    D-700 has none, and is never shown."""
    return (
        Photo.user_id == owner_id,
        Photo.kind == PhotoKind.PRIVATE,
        Photo.status == ReviewStatus.APPROVED,
        Photo.scored_key.is_not(None),
    )


async def lock_requester(session: AsyncSession, requester_id: UUID) -> None:
    """Hold the requester's album requests until this transaction ends: two
    requests at once are one after the other, so the second finds the first."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock, hashtext(CAST(:r AS text)))"),
        {"lock": REQUESTER_LOCK, "r": str(requester_id)},
    )


async def live_request(
    session: AsyncSession, requester_id: UUID, owner_id: UUID
) -> AlbumRequest | None:
    found: AlbumRequest | None = await session.scalar(
        select(AlbumRequest)
        .where(
            AlbumRequest.requester_id == requester_id,
            AlbumRequest.owner_id == owner_id,
            AlbumRequest.status.in_(LIVE),
        )
        .execution_options(populate_existing=True)
    )
    return found


async def last_closed_at(
    session: AsyncSession, requester_id: UUID, owner_id: UUID
) -> datetime | None:
    """When she last declined or revoked one of his requests, if ever."""
    found: datetime | None = await session.scalar(
        select(func.max(AlbumRequest.decided_at)).where(
            AlbumRequest.requester_id == requester_id,
            AlbumRequest.owner_id == owner_id,
            AlbumRequest.status.in_(CLOSED),
        )
    )
    return found


async def latest_request(
    session: AsyncSession, requester_id: UUID, owner_id: UUID
) -> AlbumRequest | None:
    found: AlbumRequest | None = await session.scalar(
        select(AlbumRequest)
        .where(
            AlbumRequest.requester_id == requester_id,
            AlbumRequest.owner_id == owner_id,
        )
        .order_by(AlbumRequest.created_at.desc(), AlbumRequest.id.desc())
        .limit(1)
    )
    return found


async def albumable_count(session: AsyncSession, owner_id: UUID) -> int:
    found = await session.scalar(
        select(func.count()).select_from(Photo).where(*_albumable(owner_id))
    )
    return int(found or 0)


async def albumable_photos(session: AsyncSession, owner_id: UUID) -> list[Photo]:
    """The photos the album shows, oldest first."""
    rows = await session.scalars(
        select(Photo).where(*_albumable(owner_id)).order_by(Photo.created_at, Photo.id)
    )
    return list(rows)


async def add(
    session: AsyncSession,
    *,
    requester_id: UUID,
    owner_id: UUID,
    at: datetime,
) -> AlbumRequest:
    """The request, flushed so its id names the debit. `at` is the clock's
    now, never the transaction's `now()`."""
    row = AlbumRequest(
        requester_id=requester_id,
        owner_id=owner_id,
        status=AlbumRequestStatus.PENDING,
        credits_charged=0,
        created_at=at,
    )
    session.add(row)
    await session.flush()
    return row


async def request_for_update(
    session: AsyncSession, request_id: UUID, *, owner_id: UUID | None = None
) -> AlbumRequest | None:
    """The request, locked until the transaction ends; with `owner_id`, only
    if it is hers."""
    query = select(AlbumRequest).where(AlbumRequest.id == request_id)
    if owner_id is not None:
        query = query.where(AlbumRequest.owner_id == owner_id)
    found: AlbumRequest | None = await session.scalar(
        query.with_for_update().execution_options(populate_existing=True)
    )
    return found


async def requester_columns(
    session: AsyncSession, request_ids: Sequence[UUID]
) -> Sequence[Row[Any]]:
    """Each request with its requester's card-lite columns."""
    return (
        await session.execute(
            _with_requester(select(AlbumRequest)).where(
                AlbumRequest.id.in_(request_ids)
            )
        )
    ).all()


def _with_requester(query: Any) -> Any:
    requester = aliased(User)
    profile = aliased(Profile)
    return (
        query.add_columns(
            requester.status.label("requester_status"),
            requester.last_active_at.label("requester_last_active_at"),
            profile.first_name.label("requester_first_name"),
            profile.username.label("requester_username"),
            main_photo_key(requester.id).label("requester_photo_key"),
            badge_of(requester.id, requester.is_verified).label("requester_badge"),
        )
        .join(requester, requester.id == AlbumRequest.requester_id)
        .join(profile, profile.user_id == requester.id)
    )


async def incoming(
    session: AsyncSession,
    owner_id: UUID,
    *,
    after: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[Row[Any]]:
    """Up to `limit` of her pending and granted requests, newest first by
    `(created_at, id)`, from just after `after`; none from across a block."""
    query = (
        _with_requester(select(AlbumRequest))
        .where(
            AlbumRequest.owner_id == owner_id,
            AlbumRequest.status.in_(LIVE),
            ~blocked_either_way(owner_id, AlbumRequest.requester_id),
        )
        .order_by(AlbumRequest.created_at.desc(), AlbumRequest.id.desc())
        .limit(limit)
    )
    if after is not None:
        query = query.where(tuple_(AlbumRequest.created_at, AlbumRequest.id) < after)
    return (await session.execute(query)).all()


async def granted_requests(session: AsyncSession, owner_id: UUID) -> list[UUID]:
    """Her granted requests: every album that may hold a copy of her photos."""
    rows = await session.scalars(
        select(AlbumRequest.id).where(
            AlbumRequest.owner_id == owner_id,
            AlbumRequest.status == AlbumRequestStatus.GRANTED,
        )
    )
    return list(rows)


# --- The copies ----------------------------------------------------------------------


async def copies(session: AsyncSession, request_id: UUID) -> list[AlbumCopy]:
    rows = await session.scalars(
        select(AlbumCopy)
        .where(AlbumCopy.request_id == request_id)
        .order_by(AlbumCopy.created_at, AlbumCopy.id)
    )
    return list(rows)


async def shown_copies(
    session: AsyncSession, request_id: UUID, owner_id: UUID
) -> list[str]:
    """The keys of the request's copies of photos the album still shows, in
    the photos' order."""
    rows = await session.scalars(
        select(AlbumCopy.file_key)
        .join(Photo, Photo.id == AlbumCopy.photo_id)
        .where(AlbumCopy.request_id == request_id, *_albumable(owner_id))
        .order_by(Photo.created_at, Photo.id)
    )
    return list(rows)


async def add_copy(
    session: AsyncSession,
    request: AlbumRequest,
    photo_id: UUID,
    file_key: str,
) -> None:
    """Record a copy; one already recorded for the photo stays as it is."""
    await session.execute(
        insert(AlbumCopy)
        .values(
            request_id=request.id,
            photo_id=photo_id,
            owner_id=request.owner_id,
            viewer_id=request.requester_id,
            file_key=file_key,
        )
        .on_conflict_do_nothing()
    )


async def delete_copy(session: AsyncSession, copy_id: UUID) -> None:
    await session.execute(delete(AlbumCopy).where(AlbumCopy.id == copy_id))


async def username_of(session: AsyncSession, user_id: UUID) -> str | None:
    found: str | None = await session.scalar(
        select(Profile.username).where(Profile.user_id == user_id)
    )
    return found
