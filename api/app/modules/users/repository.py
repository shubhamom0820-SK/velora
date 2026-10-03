"""SQL for accounts. No rules here: the services decide."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BanKind
from app.modules.auth.models import BannedIdentity, Session
from app.modules.notifications.models import NotificationPrefs
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.users.models import User
from app.modules.wallet.models import Wallet


async def user_by_phone_hash(session: AsyncSession, phone_hash: str) -> User | None:
    user: User | None = await session.scalar(
        select(User).where(User.phone_hash == phone_hash)
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


# D-072: what an under-18 refusal does with each table that has a key to users.
# A test holds every such key, every table, to exactly these two lists, so a
# table added later fails CI, naming D-072, until someone decides which it is.
#
# Deleted with the account: signup's four, and the picks a later step makes.
UNDERAGE_DELETES = (
    Session,
    NotificationPrefs,
    Wallet,
    ProfileIntent,
    ProfileInterest,
    Profile,
)
# Kept, each with why a user at the dob step can't have a row there. Their keys
# are RESTRICT, so if one ever does, the deletion fails whole: a 500, and the
# minor's account kept, the very thing D-072 exists to prevent. D-078 settles
# it: P-54 moves every table here but rule 12's five (messages, reports,
# ledger_entries, payments, audit_log) to the deletions, and photos and
# verifications go with their files, keys read before the rows are deleted.
UNDERAGE_KEEPS = {
    "album_requests": "T-8.4, onboarded users only",
    "audit_log": "rule 12; its key is the staff member acting",
    "blocks": "T-9.1, onboarded users only",
    "fraud_events": "T-9.2's signals; it must not record one before dob is set",
    "fraud_scores": "T-9.2's worker; it must not score a user before dob is set",
    "gift_sends": "T-8.9, onboarded users only; money",
    "kudos": "T-8.5, onboarded users only",
    "ledger_entries": "rule 12; money",
    "liked_you_reveals": "T-6.7, onboarded users only; money",
    "matches": "T-6.4, onboarded users only",
    "message_unlocks": "T-7.9, onboarded users only; money",
    "messages": "rule 12",
    "notifications": "T-9.4, onboarded users only",
    "payments": "rule 12; money",
    "photos": "T-4.2; deleted with its files by P-54 (D-078)",
    "profile_views": "T-6.3, onboarded users only",
    "push_subscriptions": "T-9.4, onboarded users only",
    "referrals": "T-8.6, which applies a code during onboarding; P-54 (D-078)",
    "refund_requests": "T-8.3, onboarded users only; money",
    "reports": "rule 12",
    "swipes": "T-6.4, onboarded users only",
    "thread_clears": "T-7.8, onboarded users only",
    "threads": "T-7.1, onboarded users only",
    "verifications": "T-4.5; deleted with its selfies by P-54 (D-078)",
}


async def delete_account(session: AsyncSession, user_id: UUID) -> None:
    """Delete the user and everything attached, in the caller's transaction."""
    for model in UNDERAGE_DELETES:
        await session.execute(
            delete(model)
            .where(model.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
    deleted = await session.execute(
        delete(User)
        .where(User.id == user_id)
        .execution_options(synchronize_session=False)
    )
    if deleted.rowcount != 1:  # type: ignore[attr-defined]
        raise LookupError("no such user to delete")


async def ban_phone_hash(session: AsyncSession, phone_hash: str, reason: str) -> None:
    """Keep a number's hash in `banned_identities` (D-009). A hash already
    there keeps its row and reason: one row per number, whatever banned it."""
    await session.execute(
        insert(BannedIdentity)
        .values(kind=BanKind.PHONE_HASH, value=phone_hash, reason=reason)
        .on_conflict_do_nothing(index_elements=["kind", "value"])
    )


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
