"""SQL for accounts. No rules here: the services decide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BanKind
from app.modules.account.models import DataExport
from app.modules.album.models import AlbumRequest
from app.modules.auth.models import BannedIdentity, Session
from app.modules.discovery.models import ProfileView
from app.modules.gifts.models import GiftSend
from app.modules.kudos.models import Kudos
from app.modules.matches.models import Match
from app.modules.messages.models import MessageUnlock
from app.modules.notifications.models import (
    Notification,
    NotificationPrefs,
    PushSubscription,
)
from app.modules.payments.models import RefundRequest
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.referrals.models import Referral
from app.modules.safety.models import Block, FraudEvent, FraudScore
from app.modules.swipes.models import LikedYouReveal, Swipe
from app.modules.threads.models import Thread, ThreadClear
from app.modules.users.models import User
from app.modules.verification.models import Verification
from app.modules.wallet.models import Wallet


async def user_by_phone_hash(session: AsyncSession, phone_hash: str) -> User | None:
    """The live account on a number, locked until the transaction ends.

    Never an erased one (T-9.6, D-500): its hash stays on its row (D-051), and
    the number is free. The lock is the sign-in's side of the race with the
    erasure: an erasure that commits first leaves this row no longer matching,
    so the sign-in finds nothing and starts a new account; a sign-in that
    commits first has restored the account, and the erasure skips it.
    """
    user: User | None = await session.scalar(
        select(User)
        .where(User.phone_hash == phone_hash, User.anonymised_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return user


async def user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def user_for_update(session: AsyncSession, user_id: UUID) -> User | None:
    """The user, re-read and locked until the transaction ends: two onboarding
    requests at once take turns, each seeing what the other wrote."""
    user: User | None = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return user


@dataclass(frozen=True)
class Attached:
    """A table an under-18 refusal deletes from (D-078): its rows naming the
    user in any of `columns`, and, `on_threads`, every row on a thread the user
    is in, whoever's it is (another user's clear of the user's thread)."""

    model: type[Any]
    columns: tuple[str, ...]
    on_threads: bool = False


# D-072 and D-078: an under-18 refusal deletes the user's rows in every table
# the app role may delete from, in an order the keys between them allow: a
# table before any it holds a key to. Tests hold this to the database: every
# table with a key to users is here or kept below, every column naming the user
# is listed, every table with a key to threads has `on_threads`, and the order
# is the keys'. A table added later fails CI, naming D-072, until it is listed.
UNDERAGE_DELETES = (
    Attached(ThreadClear, ("user_id",), on_threads=True),
    Attached(Kudos, ("from_id", "to_id"), on_threads=True),
    Attached(GiftSend, ("sender_id", "recipient_id"), on_threads=True),
    Attached(Match, ("user_low", "user_high"), on_threads=True),
    Attached(MessageUnlock, ("user_id",)),
    Attached(LikedYouReveal, ("viewer_id", "liker_id")),
    Attached(Swipe, ("swiper_id", "target_id")),
    Attached(ProfileView, ("viewer_id", "viewed_id")),
    Attached(Block, ("blocker_id", "blocked_id")),
    Attached(AlbumRequest, ("requester_id", "owner_id")),
    Attached(Referral, ("referee_id", "referrer_id")),
    Attached(RefundRequest, ("user_id",)),
    Attached(Notification, ("user_id",)),
    Attached(PushSubscription, ("user_id",)),
    Attached(FraudEvent, ("user_id",)),
    Attached(FraudScore, ("user_id",)),
    Attached(DataExport, ("user_id",)),
    # A selfie is a photo (kind `selfie`), so its file is a photo's: listed in
    # UNDERAGE_FILES below, read before these rows go (D-078, T-4.2).
    Attached(Verification, ("user_id",)),
    Attached(Photo, ("user_id",)),
    Attached(Thread, ("user_low", "user_high", "opened_by")),
    Attached(Session, ("user_id",)),
    Attached(NotificationPrefs, ("user_id",)),
    Attached(Wallet, ("user_id",)),
    Attached(ProfileIntent, ("user_id",)),
    Attached(ProfileInterest, ("user_id",)),
    Attached(Profile, ("user_id",)),
)
# Kept: rule 12's, which nothing hard-deletes and the app role can't (T-1.22).
# A user at the dob step can't have a row in any of them; if one ever does, the
# deletion fails whole, a 500, and the bug is in whatever wrote it (D-078).
UNDERAGE_KEEPS = {
    "audit_log": "rule 12; its key is the staff member acting",
    "ledger_entries": "rule 12; money",
    "messages": "rule 12",
    "payments": "rule 12; money",
    "reports": "rule 12",
}


@dataclass(frozen=True)
class FileColumn:
    """A column holding a storage key behind a user's row, and which bucket
    that key is in (D-027)."""

    model: type[Any]
    column: str
    bucket: Literal["public", "private"]


# D-078's file half (T-4.2): every storage key behind a row the deletion takes,
# read in the deleting transaction before the rows go. A test holds it to the
# schema: every `*_key` column on a table in UNDERAGE_DELETES is here.
UNDERAGE_FILES = (
    FileColumn(Photo, "raw_key", "private"),
    FileColumn(Photo, "public_key", "public"),
    FileColumn(DataExport, "file_key", "private"),
)


async def files_of(
    session: AsyncSession, user_id: UUID
) -> list[tuple[Literal["public", "private"], str]]:
    """Every stored file behind the user's rows, as (bucket, key)."""
    found: list[tuple[Literal["public", "private"], str]] = []
    for file in UNDERAGE_FILES:
        column = getattr(file.model, file.column)
        keys = await session.scalars(
            select(column).where(file.model.user_id == user_id, column.is_not(None))
        )
        found.extend((file.bucket, key) for key in keys)
    return found


async def user_exists(session: AsyncSession, user_id: UUID) -> bool:
    found: bool = bool(await session.scalar(select(exists().where(User.id == user_id))))
    return found


async def delete_account(session: AsyncSession, user_id: UUID) -> None:
    """Delete the user and everything attached, in the caller's transaction."""
    users_threads = select(Thread.id).where(
        or_(
            Thread.user_low == user_id,
            Thread.user_high == user_id,
            Thread.opened_by == user_id,
        )
    )
    for attached in UNDERAGE_DELETES:
        model = attached.model
        naming = [getattr(model, column) == user_id for column in attached.columns]
        if attached.on_threads:
            naming.append(model.thread_id.in_(users_threads))
        await session.execute(
            delete(model)
            .where(or_(*naming))
            .execution_options(synchronize_session=False)
        )
    deleted = await session.execute(
        delete(User)
        .where(User.id == user_id)
        .execution_options(synchronize_session=False)
    )
    if deleted.rowcount != 1:  # type: ignore[attr-defined]
        raise LookupError("no such user to delete")


async def ban_phone_hash(session: AsyncSession, phone_hash: str, reason: str) -> UUID:
    """Keep a number's hash in `banned_identities` (D-009), and return its row's
    id. A hash already there keeps its row and reason: one row per number,
    whatever banned it."""
    await session.execute(
        insert(BannedIdentity)
        .values(kind=BanKind.PHONE_HASH, value=phone_hash, reason=reason)
        .on_conflict_do_nothing(index_elements=["kind", "value"])
    )
    row_id = await session.scalar(
        select(BannedIdentity.id).where(
            BannedIdentity.kind == BanKind.PHONE_HASH,
            BannedIdentity.value == phone_hash,
        )
    )
    if row_id is None:  # inserted or kept just above, in this transaction
        raise LookupError("the ban was neither written nor found")
    return row_id


async def take_pin_try(session: AsyncSession, user_id: UUID, limit: int) -> int | None:
    """Count one PIN try, if fewer than `limit` are counted, and return the new
    count; None if `limit` already are. One statement, so tries made at once
    are each counted once, and no more than `limit` are ever taken (D-069)."""
    taken: int | None = await session.scalar(
        update(User)
        .where(User.id == user_id, User.pin_failed < limit)
        .values(pin_failed=User.pin_failed + 1)
        .returning(User.pin_failed)
        .execution_options(synchronize_session=False)
    )
    return taken


async def give_back_pin_try(session: AsyncSession, user_id: UUID) -> None:
    """Uncount a try that turned out not to be a guess: the stored hash
    couldn't be checked (D-069)."""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(pin_failed=func.greatest(User.pin_failed - 1, 0))
        .execution_options(synchronize_session=False)
    )


async def clear_pin_tries(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(pin_failed=0)
        .execution_options(synchronize_session=False)
    )


async def referral_code_taken(session: AsyncSession, code: str) -> bool:
    """Whether any user has `code`, in any case: the column is citext."""
    taken = await session.scalar(select(exists().where(User.referral_code == code)))
    return bool(taken)


async def insert_account(
    session: AsyncSession, *, phone_hash: str, phone_enc: bytes, referral_code: str
) -> tuple[User, Profile]:
    """The four rows signup creates: the user, an empty profile, a wallet at the
    column's default of 0 (its balance is written only by wallet.service, rule
    5), and notification preferences at their defaults."""
    user = User(phone_hash=phone_hash, phone_enc=phone_enc, referral_code=referral_code)
    session.add(user)
    await session.flush()
    profile = Profile(user_id=user.id)
    session.add_all(
        [profile, Wallet(user_id=user.id), NotificationPrefs(user_id=user.id)]
    )
    await session.flush()
    await session.refresh(user)
    await session.refresh(profile)
    return user, profile


async def profile_of(session: AsyncSession, user_id: UUID) -> Profile:
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise LookupError("a user without a profile: signup creates both")
    return profile


async def balance_of(session: AsyncSession, user_id: UUID) -> int:
    balance = await session.scalar(
        select(Wallet.balance).where(Wallet.user_id == user_id)
    )
    if balance is None:
        raise LookupError("a user without a wallet: signup creates both")
    return balance


async def intent_ids_of(session: AsyncSession, user_id: UUID) -> list[int]:
    rows = await session.scalars(
        select(ProfileIntent.intent_id)
        .where(ProfileIntent.user_id == user_id)
        .order_by(ProfileIntent.intent_id)
    )
    return list(rows)


async def interest_ids_of(session: AsyncSession, user_id: UUID) -> list[int]:
    rows = await session.scalars(
        select(ProfileInterest.interest_id)
        .where(ProfileInterest.user_id == user_id)
        .order_by(ProfileInterest.interest_id)
    )
    return list(rows)
