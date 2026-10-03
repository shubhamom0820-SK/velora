"""Accounts: finding or creating one by phone number, and `Me` (T-3.3)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
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
