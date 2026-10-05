"""Finishing onboarding (T-4.8, D-310): the `selfie` step's way to `done`.

A man's "Skip for now" and a match's "Continue" both end here, and this, not
the screen, decides: every requirement met, and a selfie that matched for
anyone but a man (D-008). It follows D-068's rule as every step does: before
`selfie`, `ONBOARDING_INCOMPLETE`; at it, it finishes; once `done`, it changes
nothing. The user's row is locked first, as every onboarding write and the
selfie's decision lock it, so what it reads is what they last wrote.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep
from app.core.errors import AppError
from app.modules.onboarding import repository, rules
from app.modules.profiles.models import Profile
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import Me


async def complete(session: AsyncSession, user: User) -> Me:
    async with session.begin():
        user = await users_service.locked_user(session, user.id)
        if not users_service.at_step(user, OnboardingStep.SELFIE):
            return await users_service.me(session, user)
        profile = await repository.profile_of(session, user.id)
        facts = await facts_of(session, profile)
        missing = rules.missing(facts)
        if missing:
            raise AppError(
                "PROFILE_INCOMPLETE",
                "Finish your profile first.",
                status=403,
                details={"missing": missing},
            )
        # T-4.5's own word on the selfie: set with the verification's
        # `approved`, in the same transaction, and what `start` reads.
        if rules.needs_a_match(user.gender) and not user.is_verified:
            raise AppError(
                "VERIFICATION_REQUIRED",
                "Your selfie has to match your photos first.",
                status=403,
            )
        profile.completeness = rules.completeness(facts.approved_photos)
        users_service.advance_past(user, OnboardingStep.SELFIE)
        return await users_service.me(session, user)


async def facts_of(session: AsyncSession, profile: Profile) -> rules.Facts:
    """What the requirements read from `profile`, in the caller's
    transaction. The dev seed reads its finished profiles the same way."""
    user_id = profile.user_id
    return rules.Facts(
        seeking=profile.seeking,
        intents=await repository.intent_count(session, user_id),
        first_name=profile.first_name,
        hometown=profile.hometown,
        city=profile.city,
        located=profile.location is not None,
        username=profile.username,
        about=profile.about,
        approved_photos=await repository.approved_public_photo_count(session, user_id),
        interests=await repository.interest_count(session, user_id),
    )
