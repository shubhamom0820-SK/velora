"""Accounts: finding or creating one by phone number, and `Me` (T-3.3)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, ratelimit
from app.core.config import Settings
from app.core.enums import Gender, OnboardingStep, UserStatus
from app.core.errors import AppError, invalid_field
from app.core.queue import DELETE_FILES, DELETE_FILES_FIRST_CHECK, Queue
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


# --- Onboarding (T-3.6): the step rule, dob and gender ---------------------------

# In the order `onboarding_t` declares them, which is the order they're asked.
_STEPS = tuple(OnboardingStep)


def at_step(user: User, step: OnboardingStep) -> bool:
    """D-068's rule for every onboarding endpoint: True if the user is at
    `step`, so the endpoint advances it; False once they're past it, so it is
    an edit that doesn't; `ONBOARDING_INCOMPLETE`, naming the step they're at,
    if they haven't reached it."""
    here, there = _STEPS.index(user.onboarding_step), _STEPS.index(step)
    if here < there:
        raise AppError(
            "ONBOARDING_INCOMPLETE",
            "Finish the earlier steps first.",
            status=403,
            details={"step": user.onboarding_step.value},
        )
    return here == there


def advance_past(user: User, step: OnboardingStep) -> None:
    user.onboarding_step = _STEPS[_STEPS.index(step) + 1]


async def locked_user(session: AsyncSession, user_id: UUID) -> User:
    """The user, re-read and locked for the caller's transaction, so the step
    and the fields an onboarding write checks are the ones it changes."""
    user = await repository.user_for_update(session, user_id)
    if user is None:
        raise LookupError("no such user")
    return user


# --- The PIN's row (T-3.9): auth.service decides, these keep the count -----------


async def take_pin_try(session: AsyncSession, user_id: UUID, limit: int) -> int | None:
    return await repository.take_pin_try(session, user_id, limit)


async def give_back_pin_try(session: AsyncSession, user_id: UUID) -> None:
    await repository.give_back_pin_try(session, user_id)


async def clear_pin_tries(session: AsyncSession, user_id: UUID) -> None:
    await repository.clear_pin_tries(session, user_id)


def store_pin(user: User, pin_hash: str) -> None:
    """A new PIN starts with no wrong tries against it."""
    user.pin_hash = pin_hash
    user.pin_failed = 0


async def skip_pin(session: AsyncSession, user: User) -> Me:
    """`POST /me/pin/skip`: the PIN is optional, so its step can be passed
    without one, moving `pin` to `selfie` (D-069); after the step, nothing to do."""
    async with session.begin():
        user = await locked_user(session, user.id)
        if at_step(user, OnboardingStep.PIN):
            advance_past(user, OnboardingStep.PIN)
        return await me(session, user)


# D-009: a hard 18+ gate, by age in IST today. A date further back than this is
# a typo, not a person.
ADULT_AGE = 18
OLDEST_DOB_YEARS = 100
UNDERAGE_REASON = "underage"


async def set_dob(
    session: AsyncSession, user: User, dob: date, *, queue: Queue, settings: Settings
) -> Me:
    """Set the date of birth once, at the dob step.

    Under 18 is D-072: the account and everything attached are deleted in this
    transaction, only the number's hash is kept in `banned_identities`, and the
    answer is `UNDERAGE`, sent once the deletion has committed.

    Files go too, in D-090's order: their keys read before the rows go, and
    their deletion queued before the commit, to run once the user is gone. A
    refusal with no files queues nothing.
    """
    today = clock.today_ist()
    async with session.begin():
        user = await locked_user(session, user.id)
        advancing = at_step(user, OnboardingStep.DOB)
        if user.dob is not None:
            raise _immutable()
        _refuse_an_impossible_dob(dob, today)
        if age_on(dob, today) >= ADULT_AGE:
            user.dob = dob
            if advancing:
                advance_past(user, OnboardingStep.DOB)
            await _flush_identity(session)
            return await me(session, user)
        files = await repository.files_of(session, user.id)
        banned_id = await repository.ban_phone_hash(
            session, user.phone_hash, UNDERAGE_REASON
        )
        await repository.delete_account(session, user.id)
        if files:
            buckets = {
                "public": settings.R2_BUCKET_PUBLIC,
                "private": settings.R2_BUCKET_PRIVATE,
            }
            await queue.enqueue(
                DELETE_FILES,
                job_id=f"{DELETE_FILES}:{user.id}",
                defer_by=DELETE_FILES_FIRST_CHECK,
                user_id=str(user.id),
                banned_id=str(banned_id),
                objects=[[buckets[bucket], key] for bucket, key in files],
            )
    session.expunge(user)
    raise AppError(
        "UNDERAGE",
        "You must be 18 or older to sign up.",
        status=422,
    )


async def account_exists(session: AsyncSession, user_id: UUID) -> bool:
    """Whether the user still has an account: D-090's deletion job asks before
    it deletes a file."""
    return await repository.user_exists(session, user_id)


def _refuse_an_impossible_dob(dob: date, today: date) -> None:
    if dob > today:
        raise invalid_field("dob", "is in the future")
    if dob < _years_before(today, OLDEST_DOB_YEARS):
        raise invalid_field("dob", f"is more than {OLDEST_DOB_YEARS} years ago")


def _years_before(day: date, years: int) -> date:
    """The same day `years` earlier; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


async def set_gender(session: AsyncSession, user: User, gender: Gender) -> Me:
    """Set gender once, at the gender step; never again (D-068). Changing it
    after signup is rejected permanently (CLAUDE.md)."""
    async with session.begin():
        user = await locked_user(session, user.id)
        advancing = at_step(user, OnboardingStep.GENDER)
        if user.gender is not None:
            raise _immutable()
        user.gender = gender
        if advancing:
            advance_past(user, OnboardingStep.GENDER)
        await _flush_identity(session)
        return await me(session, user)


# T-1.9's trigger refuses a change to a set gender or dob with this SQLSTATE,
# behind the checks above: it catches any write that gets past them. Read by
# code, never by message, which Postgres may reword. `users` has no CHECK
# constraint, so on this table only the trigger raises it.
CHECK_VIOLATION = "23514"


async def _flush_identity(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as error:
        if sqlstate_of(error) == CHECK_VIOLATION:
            raise _immutable() from None
        raise


def sqlstate_of(error: DBAPIError) -> str | None:
    """The SQLSTATE asyncpg reported, if any."""
    sqlstate = getattr(error.orig, "sqlstate", None)
    return sqlstate if isinstance(sqlstate, str) else None


def _immutable() -> AppError:
    return AppError(
        "IMMUTABLE_FIELD", "This can't be changed once it's set.", status=422
    )


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
