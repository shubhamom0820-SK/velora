"""Profiles: the onboarding steps that fill one in, from seeking (T-3.6) to
name, places, about and username (T-3.7), interests (T-3.8), and the location
question, which has no step of its own (T-4.10).

Every step follows D-068's rule, `users.service.at_step`: it works at its
step, advancing it, and after it, as an edit that doesn't advance; before it,
`ONBOARDING_INCOMPLETE`. Each write locks the user's row first, so the step it
read is the step it moves.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import OnboardingStep, Seeking
from app.core.errors import AppError, invalid_field, invalid_fields
from app.modules.profiles import repository, rules
from app.modules.profiles.models import Profile
from app.modules.profiles.schemas import (
    Area,
    Intent,
    Interest,
    UsernameAvailability,
)
from app.modules.safety import fraud
from app.modules.safety import signals as safety_signals
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import Me


async def intents(session: AsyncSession) -> list[Intent]:
    async with session.begin():
        rows = await repository.intents(session)
    return [Intent(id=row.id, slug=row.slug, label=row.label) for row in rows]


async def set_seeking(
    session: AsyncSession, user: User, seeking: Seeking, intent_ids: Sequence[int]
) -> Me:
    """Who they're looking for and why: 1 to 3 different intents from the
    catalogue (D-041), replacing the ones they had, in one transaction."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        advancing = users_service.at_step(user, OnboardingStep.SEEKING)
        chosen = set(intent_ids)
        if len(chosen) != len(intent_ids):
            raise invalid_field("intent_ids", "lists an intent twice")
        if await repository.known_intent_ids(session, chosen) != chosen:
            raise invalid_field("intent_ids", "has an id that isn't an intent")
        profile = await repository.profile_of(session, user.id)
        profile.seeking = seeking
        await repository.replace_intents(session, user.id, sorted(chosen))
        if advancing:
            users_service.advance_past(user, OnboardingStep.SEEKING)
        return await users_service.me(session, user)


# --- Interests (T-3.8) ----------------------------------------------------------------

INTERESTS_PER_PROFILE = 5


async def interests(session: AsyncSession) -> list[Interest]:
    async with session.begin():
        rows = await repository.interests(session)
    return [Interest(id=row.id, slug=row.slug, label=row.label) for row in rows]


async def set_interests(
    session: AsyncSession, user: User, interest_ids: Sequence[int]
) -> Me:
    """Exactly 5 different interests from the catalogue (03-SCHEMA), replacing
    the ones they had, in one transaction. The step comes after photos
    (D-068), so until T-4.3 only a test reaches it."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        advancing = users_service.at_step(user, OnboardingStep.INTERESTS)
        chosen = set(interest_ids)
        if len(chosen) != len(interest_ids):
            raise invalid_field("interest_ids", "lists an interest twice")
        if len(chosen) != INTERESTS_PER_PROFILE:
            raise invalid_field(
                "interest_ids", f"must be exactly {INTERESTS_PER_PROFILE}"
            )
        if await repository.known_interest_ids(session, chosen) != chosen:
            raise invalid_field("interest_ids", "has an id that isn't an interest")
        await repository.replace_interests(session, user.id, sorted(chosen))
        if advancing:
            users_service.advance_past(user, OnboardingStep.INTERESTS)
        return await users_service.me(session, user)


# --- Location (T-4.10, D-220) -------------------------------------------------------

# The question comes after Name and before Username, with no step of its own:
# it works from the `username` step on, and never moves the step. `Me` says
# whether a location is set, which is how the web knows to ask (D-220).
LOCATION_FROM = OnboardingStep.USERNAME


async def areas(session: AsyncSession, city: str | None) -> list[Area]:
    async with session.begin():
        rows = await repository.areas(session, city)
    # Every row has a city and a name, though the columns allow NULL (P-24).
    return [Area(id=row.id, city=row.city, name=row.name) for row in rows]


async def set_position(session: AsyncSession, user: User, lat: float, lng: float) -> Me:
    """A position the browser shared, inside India's box, with the nearest
    area within `AREA_WITHIN_M` of it, or none, replacing any area picked
    before (D-220). The area is found from the exact position; what is stored
    is its grid point, never the position itself (D-490)."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, LOCATION_FROM)
        problems = rules.position_problems(lat, lng)
        if problems:
            raise invalid_fields(problems)
        profile = await repository.profile_of(session, user.id)
        profile.area_id = await repository.nearest_area_id(
            session, lat, lng, within_m=rules.AREA_WITHIN_M
        )
        await _locate(session, profile, repository.point(lat, lng))
        return await users_service.me(session, user)


async def set_area(session: AsyncSession, user: User, area_id: UUID) -> Me:
    """An area picked instead: its centroid becomes the location (D-034), on
    the grid like any other (D-490)."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        users_service.at_step(user, LOCATION_FROM)
        if not await repository.area_exists(session, area_id):
            raise invalid_field("area_id", "isn't an area")
        profile = await repository.profile_of(session, user.id)
        profile.area_id = area_id
        await _locate(session, profile, repository.centroid_of(area_id))
        return await users_service.me(session, user)


async def _locate(session: AsyncSession, profile: Profile, location: object) -> None:
    """The location and its time, always together: `Me` reads the time alone.
    A move of more than `fraud.JUMP_KM` within `fraud.JUMP_WITHIN` of the last
    one is a signal (T-9.2), its distance only, never either place."""
    now = clock.now()
    last = profile.location_updated_at
    if last is not None:
        km = await repository.km_from_current(session, profile.user_id, location)
        if km is not None and fraud.jumped(km, now - last):
            await safety_signals.record_crossing(
                session, profile.user_id, fraud.LOCATION_JUMP, {"km": round(km)}
            )
    profile.location = location
    profile.location_updated_at = now


# --- Name, places and about (T-3.7) ------------------------------------------------

# `PATCH /me/profile` spans two steps (D-068): these three are `profile`'s, which
# advances once all three are set; `about` is the `about` step's.
PROFILE_FIELDS = ("first_name", "hometown", "city")
_PROBLEMS = {
    "first_name": rules.first_name_problem,
    "hometown": rules.place_problem,
    "city": rules.place_problem,
    "about": rules.about_problem,
}


async def update_profile(
    session: AsyncSession, user: User, changes: Mapping[str, str]
) -> Me:
    """Set whichever fields were sent, all or none. A field of a step the
    user hasn't reached is `ONBOARDING_INCOMPLETE`, before any is checked."""
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        at_profile = any(f in changes for f in PROFILE_FIELDS) and (
            users_service.at_step(user, OnboardingStep.PROFILE)
        )
        at_about = "about" in changes and (
            users_service.at_step(user, OnboardingStep.ABOUT)
        )
        cleaned = {field: rules.clean_text(value) for field, value in changes.items()}
        problems = {
            field: problem
            for field, value in cleaned.items()
            if (problem := _PROBLEMS[field](value)) is not None
        }
        if problems:
            raise invalid_fields(problems)
        profile = await repository.profile_of(session, user.id)
        for field, value in cleaned.items():
            setattr(profile, field, value)
        if at_profile and all(getattr(profile, f) for f in PROFILE_FIELDS):
            users_service.advance_past(user, OnboardingStep.PROFILE)
        if at_about:
            users_service.advance_past(user, OnboardingStep.ABOUT)
        return await users_service.me(session, user)


# --- Usernames (T-3.7) ----------------------------------------------------------------

_SUGGESTION_TRIES = 5


async def username_availability(
    session: AsyncSession, user: User, typed: str
) -> UsernameAvailability:
    """Whether `typed` could be this user's username: the format, then the
    reserved list, then whether someone else has it (D-068). A taken name
    comes with a free one to offer; a reserved one doesn't, since the name
    with digits after it is the impersonation the list exists to stop."""
    username = _username(typed)
    async with session.begin():
        if await _free(session, user, username):
            return UsernameAvailability(available=True)
        suggestion = None
        if not rules.is_reserved(username):
            suggestion = await _suggestion(session, user, username)
    return UsernameAvailability(available=False, suggestion=suggestion)


async def set_username(session: AsyncSession, user: User, typed: str) -> Me:
    """Set the username, stored in lowercase, at the username step or after
    it; once onboarding is done it can't change until T-9.6 designs how
    (D-068). Two people taking one name at once: the second is
    `USERNAME_TAKEN`, by the unique index."""
    username = _username(typed)
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        if user.onboarding_step is OnboardingStep.DONE:
            raise AppError(
                "IMMUTABLE_FIELD", "Your username can't be changed now.", status=422
            )
        advancing = users_service.at_step(user, OnboardingStep.USERNAME)
        if not await _free(session, user, username):
            raise _username_taken()
        profile = await repository.profile_of(session, user.id)
        profile.username = username
        if advancing:
            users_service.advance_past(user, OnboardingStep.USERNAME)
        await _flush_username(session)
        return await users_service.me(session, user)


def _username(typed: str) -> str:
    """In lowercase, and in the format, or `VALIDATION_ERROR`."""
    username = typed.lower()
    problem = rules.username_problem(username)
    if problem is not None:
        raise invalid_field("username", problem)
    return username


async def _free(session: AsyncSession, user: User, username: str) -> bool:
    """Not reserved, and nobody's but perhaps this user's own."""
    if rules.is_reserved(username):
        return False
    owner = await repository.username_owner(session, username)
    return owner is None or owner == user.id


async def _suggestion(session: AsyncSession, user: User, username: str) -> str | None:
    base = username[: rules.USERNAME_MAX - 2]
    for _ in range(_SUGGESTION_TRIES):
        candidate = f"{base}{secrets.randbelow(100):02d}"
        if await _free(session, user, candidate):
            return candidate
    return None


# The unique index on profiles.username: the one a race between two people
# taking one name trips. Read by SQLSTATE and the constraint's name, never by
# message, which Postgres may reword.
UNIQUE_VIOLATION = "23505"
USERNAME_INDEX = "uq_profiles_username"


async def _flush_username(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as error:
        if (
            users_service.sqlstate_of(error) == UNIQUE_VIOLATION
            and constraint_of(error) == USERNAME_INDEX
        ):
            raise _username_taken() from None
        raise


def constraint_of(error: IntegrityError) -> str | None:
    """The constraint asyncpg named, if any: on its own exception, which
    SQLAlchemy's wraps."""
    cause = error.orig.__cause__ if error.orig is not None else None
    name = getattr(cause, "constraint_name", None)
    return name if isinstance(name, str) else None


def _username_taken() -> AppError:
    return AppError("USERNAME_TAKEN", "That username is taken.", status=409)
