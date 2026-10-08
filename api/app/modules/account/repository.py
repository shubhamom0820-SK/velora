"""SQL for settings and data rights (T-9.6). No rules here: the services decide."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Row, delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserStatus
from app.modules.account import erasure
from app.modules.account.models import DataExport
from app.modules.album.models import AlbumRequest
from app.modules.auth.models import Session
from app.modules.gifts.models import GiftSend
from app.modules.kudos.models import Kudos
from app.modules.messages.models import Message
from app.modules.notifications.models import (
    Notification,
    NotificationPrefs,
    PushSubscription,
)
from app.modules.payments.models import Payment, RefundRequest
from app.modules.photos.models import Photo
from app.modules.profiles.models import (
    Area,
    Intent,
    Interest,
    Profile,
    ProfileIntent,
    ProfileInterest,
)
from app.modules.referrals.models import Referral
from app.modules.safety.models import Block, Report
from app.modules.swipes.models import LikedYouReveal, Swipe
from app.modules.threads.models import Thread
from app.modules.users.models import User
from app.modules.verification.models import Verification
from app.modules.wallet.models import LedgerEntry, Wallet

# --- Settings ---------------------------------------------------------------------


async def profile_for_update(session: AsyncSession, user_id: UUID) -> Profile:
    profile: Profile | None = await session.scalar(
        select(Profile).where(Profile.user_id == user_id).with_for_update()
    )
    if profile is None:
        raise LookupError("a user without a profile: signup creates both")
    return profile


async def delete_push_subscriptions(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        delete(PushSubscription)
        .where(PushSubscription.user_id == user_id)
        .execution_options(synchronize_session=False)
    )


# --- Exports ----------------------------------------------------------------------


async def latest_export(session: AsyncSession, user_id: UUID) -> DataExport | None:
    export: DataExport | None = await session.scalar(
        select(DataExport)
        .where(DataExport.user_id == user_id)
        .order_by(DataExport.created_at.desc(), DataExport.id.desc())
        .limit(1)
    )
    return export


async def insert_export(session: AsyncSession, user_id: UUID) -> DataExport:
    export = DataExport(user_id=user_id)
    session.add(export)
    await session.flush()
    await session.refresh(export)
    return export


async def export_for_update(
    session: AsyncSession, export_id: UUID
) -> DataExport | None:
    export: DataExport | None = await session.scalar(
        select(DataExport)
        .where(DataExport.id == export_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return export


async def exports_to_expire(
    session: AsyncSession, now: datetime, stuck_before: datetime
) -> list[UUID]:
    """Every export whose file should be gone, or whose row should say it
    never came: ready past its expiry; expired or failed with a file not yet
    read back as deleted; pending since before `stuck_before`."""
    rows = await session.scalars(
        select(DataExport.id).where(
            or_(
                (DataExport.status == "ready") & (DataExport.expires_at <= now),
                DataExport.status.in_(("expired", "failed"))
                & DataExport.file_key.is_not(None),
                (DataExport.status == "pending")
                & (DataExport.created_at < stuck_before),
            )
        )
    )
    return list(rows)


# --- The erasure (D-500, D-503) ----------------------------------------------------


def _due(cutoff: datetime) -> list[Any]:
    return [
        User.status == UserStatus.DELETED,
        User.anonymised_at.is_(None),
        User.deleted_requested_at <= cutoff,
    ]


async def accounts_due_for_erasure(
    session: AsyncSession, cutoff: datetime
) -> list[UUID]:
    rows = await session.scalars(
        select(User.id).where(*_due(cutoff)).order_by(User.deleted_requested_at)
    )
    return list(rows)


async def account_for_erasure(
    session: AsyncSession, user_id: UUID, cutoff: datetime
) -> User | None:
    """The account, locked, if it is still due: a sign-in that restored it
    first, holding the same lock, leaves nothing to erase (D-500)."""
    user: User | None = await session.scalar(
        select(User)
        .where(User.id == user_id, *_due(cutoff))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return user


async def files_to_erase(
    session: AsyncSession, user_id: UUID
) -> list[tuple[Literal["public", "private"], str]]:
    found: list[tuple[Literal["public", "private"], str]] = []
    for model, name, bucket in erasure.FILES:
        column = getattr(model, name)
        naming = (getattr(model, c) == user_id for c in erasure.columns_of(model))
        keys = await session.scalars(
            select(column).where(or_(*naming), column.is_not(None))
        )
        found.extend((bucket, key) for key in keys)
    return found


async def erase_rows(session: AsyncSession, user_id: UUID) -> None:
    """Delete every row naming the user in an `ERASED` column, in its order."""
    for erased in erasure.ERASED:
        model = erased.model
        await session.execute(
            delete(model)
            .where(
                or_(*(getattr(model, column) == user_id for column in erased.columns))
            )
            .execution_options(synchronize_session=False)
        )


# --- The export's reads (D-502) ----------------------------------------------------
#
# Each read is the user's own rows, and selects only columns that are theirs:
# never another person's id, name, number, location or words.


async def own_location(session: AsyncSession, user_id: UUID) -> Row[Any] | None:
    row = (
        await session.execute(
            text(
                "select st_y(location::geometry) as latitude, "
                "st_x(location::geometry) as longitude, location_updated_at "
                "from profiles where user_id = :u and location is not null"
            ),
            {"u": user_id},
        )
    ).first()
    return row


async def area_name(session: AsyncSession, area_id: UUID) -> str | None:
    name: str | None = await session.scalar(select(Area.name).where(Area.id == area_id))
    return name


async def intent_labels(session: AsyncSession, user_id: UUID) -> list[str]:
    rows = await session.scalars(
        select(Intent.label)
        .join(ProfileIntent, ProfileIntent.intent_id == Intent.id)
        .where(ProfileIntent.user_id == user_id)
        .order_by(Intent.id)
    )
    return list(rows)


async def interest_labels(session: AsyncSession, user_id: UUID) -> list[str]:
    rows = await session.scalars(
        select(Interest.label)
        .join(ProfileInterest, ProfileInterest.interest_id == Interest.id)
        .where(ProfileInterest.user_id == user_id)
        .order_by(Interest.id)
    )
    return [label for label in rows if label is not None]


async def live_photos(session: AsyncSession, user_id: UUID) -> list[Photo]:
    rows = await session.scalars(
        select(Photo)
        .where(Photo.user_id == user_id)
        .order_by(Photo.created_at, Photo.id)
    )
    return list(rows)


async def verifications(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    return list(
        await session.execute(
            select(Verification.status, Verification.created_at)
            .where(Verification.user_id == user_id)
            .order_by(Verification.created_at)
        )
    )


async def threads(session: AsyncSession, user_id: UUID) -> list[Thread]:
    rows = await session.scalars(
        select(Thread)
        .where(or_(Thread.user_low == user_id, Thread.user_high == user_id))
        .order_by(Thread.created_at, Thread.id)
    )
    return list(rows)


async def sent_messages(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    """The user's own messages, as shown (`body`), never `body_raw`, which is
    moderation's alone (03-SCHEMA)."""
    return list(
        await session.execute(
            select(
                Message.thread_id,
                Message.kind,
                Message.body,
                Message.media_key,
                Message.duration_s,
                Message.created_at,
            )
            .where(Message.sender_id == user_id)
            .order_by(Message.created_at, Message.id)
        )
    )


async def own_swipes(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    return list(
        await session.execute(
            select(Swipe.dir, Swipe.created_at)
            .where(Swipe.swiper_id == user_id)
            .order_by(Swipe.created_at)
        )
    )


async def own_reveals(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    return list(
        await session.execute(
            select(LikedYouReveal.created_at)
            .where(LikedYouReveal.viewer_id == user_id)
            .order_by(LikedYouReveal.created_at)
        )
    )


async def own_blocks(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    return list(
        await session.execute(
            select(Block.created_at)
            .where(Block.blocker_id == user_id)
            .order_by(Block.created_at)
        )
    )


async def reports_filed(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    """Reports the user made. Never reports about them: a reported person is
    never told who reported, or that anyone did (T-9.1)."""
    return list(
        await session.execute(
            select(Report.reason, Report.details, Report.status, Report.created_at)
            .where(Report.reporter_id == user_id)
            .order_by(Report.created_at)
        )
    )


async def kudos(
    session: AsyncSession, user_id: UUID, side: Literal["given", "received"]
) -> list[Row[Any]]:
    column = Kudos.from_id if side == "given" else Kudos.to_id
    return list(
        await session.execute(
            select(Kudos.kind, Kudos.created_at)
            .where(column == user_id)
            .order_by(Kudos.created_at)
        )
    )


async def gifts(
    session: AsyncSession, user_id: UUID, side: Literal["sent", "received"]
) -> list[Row[Any]]:
    column = GiftSend.sender_id if side == "sent" else GiftSend.recipient_id
    return list(
        await session.execute(
            select(GiftSend.gift_id, GiftSend.credits_charged, GiftSend.created_at)
            .where(column == user_id)
            .order_by(GiftSend.created_at)
        )
    )


async def album_requests(
    session: AsyncSession, user_id: UUID, side: Literal["made", "received"]
) -> list[Row[Any]]:
    column = AlbumRequest.requester_id if side == "made" else AlbumRequest.owner_id
    return list(
        await session.execute(
            select(
                AlbumRequest.status,
                AlbumRequest.credits_charged,
                AlbumRequest.created_at,
                AlbumRequest.decided_at,
            )
            .where(column == user_id)
            .order_by(AlbumRequest.created_at)
        )
    )


async def balance(session: AsyncSession, user_id: UUID) -> int | None:
    value: int | None = await session.scalar(
        select(Wallet.balance).where(Wallet.user_id == user_id)
    )
    return value


async def ledger(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    """Never `ref_id`: a super like's names the other person."""
    return list(
        await session.execute(
            select(
                LedgerEntry.reason,
                LedgerEntry.delta,
                LedgerEntry.balance_after,
                LedgerEntry.created_at,
            )
            .where(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.created_at, LedgerEntry.id)
        )
    )


async def payments(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    """Never `raw_webhook`: the provider's payload is ours to check, not a
    record of the user's."""
    return list(
        await session.execute(
            select(
                Payment.pack_id,
                Payment.amount_paise,
                Payment.credits,
                Payment.bonus_credits,
                Payment.provider,
                Payment.provider_order_id,
                Payment.provider_payment_id,
                Payment.status,
                Payment.paid_at,
                Payment.created_at,
            )
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at)
        )
    )


async def refund_requests(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    return list(
        await session.execute(
            select(RefundRequest.reason, RefundRequest.status, RefundRequest.created_at)
            .where(RefundRequest.user_id == user_id)
            .order_by(RefundRequest.created_at)
        )
    )


async def referral(session: AsyncSession, user_id: UUID) -> Row[Any] | None:
    """Whether the user was referred, and rewarded; never by whom."""
    return (
        await session.execute(
            select(Referral.created_at, Referral.rewarded_at).where(
                Referral.referee_id == user_id
            )
        )
    ).first()


async def notifications(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    """Kind and time only: a payload names the other person."""
    return list(
        await session.execute(
            select(Notification.kind, Notification.created_at, Notification.read_at)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at)
        )
    )


async def notification_prefs(
    session: AsyncSession, user_id: UUID
) -> NotificationPrefs | None:
    return await session.get(NotificationPrefs, user_id)


async def sessions(session: AsyncSession, user_id: UUID) -> list[Row[Any]]:
    return list(
        await session.execute(
            select(Session.created_at, Session.expires_at, Session.revoked_at)
            .where(Session.user_id == user_id)
            .order_by(Session.created_at)
        )
    )
