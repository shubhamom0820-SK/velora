"""SQL for accounts. No rules here: the services decide."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, exists, select
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


# The tables a user can have rows in at the dob step: signup's four, and the
# picks a later step makes. Nothing else is deleted with an account (D-072);
# every other table's key to users is RESTRICT, so a row anywhere else makes
# the deletion fail whole rather than take moderation or money records with it
# (rule 12). A test holds every foreign key into users to exactly this split.
UNDERAGE_DELETES = (
    Session,
    NotificationPrefs,
    Wallet,
    ProfileIntent,
    ProfileInterest,
    Profile,
)


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
