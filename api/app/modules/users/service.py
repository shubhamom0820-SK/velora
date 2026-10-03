"""Accounts: finding or creating one by phone number, and `Me` (T-3.3)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, ratelimit
from app.core.config import Settings
from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.security import E164, encrypt_phone, hash_phone
from app.modules.profiles.models import Profile
from app.modules.users import repository
from app.modules.users.models import User
from app.modules.users.schemas import Me, MeProfile

# Crockford's base32 without 0 and 1 (it already leaves out I, L, O and U), in
# capitals: nothing a person reading a code aloud can confuse (T-3.3). Eight of
# them is 30^8, about 6.6 × 10^11 codes.
REFERRAL_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
REFERRAL_LENGTH = 8
# A collision is a one-in-billions event; a loop that hit this many in a row
# would mean the generator is broken, not unlucky.
_REFERRAL_TRIES = 10


@dataclass(frozen=True)
class Account:
    user: User
    profile: Profile


# `last_active_at` moves at most once a minute per user (03-SCHEMA): a write per
# request would be one per swipe. A one-place window, so the clock moves it.
ACTIVITY_WINDOW_S = 60


async def user_for_request(
    session: AsyncSession, redis: Redis, user_id: UUID
) -> User | None:
    """The user an access token names, as `deps.current_user` loads them on
    every authenticated request: None if there is none any more (D-072
    deletes an under-18 account while its token lives on), refused by status
    (D-067), and noted as active, at most once a minute. Runs in its own short
    transaction, so the route's service can open another."""
    async with session.begin():
        user = await repository.user_by_id(session, user_id)
        if user is None:
            return None
        refuse_who_may_not_sign_in(user)
        noted = await ratelimit.hit(
            redis, "last_active", str(user.id), limit=1, window_s=ACTIVITY_WINDOW_S
        )
        if noted.allowed:
            user.last_active_at = clock.now()
    return user


async def me_for(session: AsyncSession, user: User) -> Me:
    async with session.begin():
        return await me(session, user)


async def get_user(session: AsyncSession, user_id: UUID) -> User:
    """The user a session or token names. Users are never hard-deleted, but
    for D-072's under-18 refusal, which leaves no session behind."""
    user = await repository.user_by_id(session, user_id)
    if user is None:
        raise LookupError("no such user")
    return user


def new_referral_code() -> str:
    return "".join(secrets.choice(REFERRAL_ALPHABET) for _ in range(REFERRAL_LENGTH))


async def find_or_create_account(
    session: AsyncSession, phone: E164, settings: Settings
) -> tuple[User, bool]:
    """The account for `phone`, and whether it was created just now.

    Runs in the caller's transaction, so the four rows are written together or
    not at all. A number signing up twice at once finds the account the other
    created rather than failing.
    """
    phone_hash = hash_phone(phone, settings)
    user = await repository.user_by_phone_hash(session, phone_hash)
    if user is not None:
        return user, False
    try:
        async with session.begin_nested():
            account = await create_account(session, phone, settings)
    except IntegrityError:
        user = await repository.user_by_phone_hash(session, phone_hash)
        if user is None:
            raise
        return user, False
    return account.user, True


async def create_account(
    session: AsyncSession,
    phone: E164,
    settings: Settings,
    *,
    referral_code: str | None = None,
) -> Account:
    """A new account for `phone`: its four rows, in the caller's transaction.

    The referral code is drawn until one is free. Only the dev seed's three
    test accounts pass one of their own (T-1.15): test accounts may be special,
    and T-8.6 looks codes up without checking their format.
    """
    code = referral_code
    if code is None:
        for _ in range(_REFERRAL_TRIES):
            code = new_referral_code()
            if not await repository.referral_code_taken(session, code):
                break
        else:
            raise RuntimeError("no free referral code in ten draws")
    user, profile = await repository.insert_account(
        session,
        phone_hash=hash_phone(phone, settings),
        phone_enc=encrypt_phone(phone, settings),
        referral_code=code,
    )
    return Account(user=user, profile=profile)


# Who may sign in and use the API (D-067): an allowlist, so a status added
# later can't until someone decides. Paused people may: pausing hides a
# profile, not an account. Sign-in, refresh and every authenticated request
# (deps.current_user) apply the same rule, so a ban takes effect at once.
MAY_SIGN_IN = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})


def refuse_who_may_not_sign_in(user: User) -> None:
    """Banned and frozen accounts get their own codes; `deleted` can't happen
    before T-9.6, which decides, so until then it's FORBIDDEN, like anything
    else not on the list."""
    if user.status in MAY_SIGN_IN:
        return
    if user.status is UserStatus.BANNED:
        raise account_banned()
    if user.status is UserStatus.FROZEN:
        raise AppError(
            "ACCOUNT_FROZEN",
            "This account is frozen while we look into it.",
            status=403,
        )
    raise AppError("FORBIDDEN", "This account can't sign in.", status=403)


def account_banned() -> AppError:
    return AppError("ACCOUNT_BANNED", "This account has been banned.", status=403)


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


async def me(session: AsyncSession, user: User) -> Me:
    """`Me` for `user`: their age in IST today, never the date itself."""
    profile = await repository.profile_of(session, user.id)
    return Me(
        id=user.id,
        role=user.role,
        status=user.status,
        onboarding_step=user.onboarding_step,
        gender=user.gender,
        age=None if user.dob is None else age_on(user.dob, clock.today_ist()),
        is_verified=user.is_verified,
        has_pin=user.pin_hash is not None,
        referral_code=user.referral_code,
        balance=await repository.balance_of(session, user.id),
        profile=MeProfile(
            first_name=profile.first_name,
            username=profile.username,
            about=profile.about,
            hometown=profile.hometown,
            city=profile.city,
            seeking=profile.seeking,
            intent_ids=await repository.intent_ids_of(session, user.id),
            interest_ids=await repository.interest_ids_of(session, user.id),
            is_hidden=profile.is_hidden,
            hide_age=profile.hide_age,
            hide_distance=profile.hide_distance,
            show_kudos=profile.show_kudos,
            show_gifts=profile.show_gifts,
        ),
    )
