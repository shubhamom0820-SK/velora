"""Profiles: the onboarding steps that fill one in, from seeking (T-3.6).

Every step follows D-068's rule, `users.service.at_step`: it works at its
step, advancing it, and after it, as an edit that doesn't advance; before it,
`ONBOARDING_INCOMPLETE`. Each write locks the user's row first, so the step it
read is the step it moves.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep, Seeking
from app.core.errors import invalid_field
from app.modules.profiles import repository
from app.modules.profiles.schemas import Intent
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
