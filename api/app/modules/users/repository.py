"""SQL for accounts. No rules here: the services decide."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

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
