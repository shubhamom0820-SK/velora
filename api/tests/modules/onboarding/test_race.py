"""Finishing while moderation decides the only photo (T-4.8): `complete` locks
the user's row first, as moderation's decision does (T-4.4), so the two take
turns, and finishing reads the photo as it was decided.

Without the lock it reads the photo as pending while the decision is still
uncommitted, and refuses a profile that is complete the moment it commits.
The overlap is forced and observed, not hoped for: the decision holds the row,
the finish starts, and the test sees Postgres make it wait before the decision
commits.

Committed for real, on a fresh man, never deleted (tests/committed.py), and
put back afterwards to what a fresh man is, never onboarded: rows naming an
intent or an interest would stop those catalogues' downgrades
(`test_migrations_round_trip`), and a location would join the seed's checks of
every located profile.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus, Seeking
from app.modules.onboarding import service
from app.modules.photos.models import Photo
from app.modules.profiles import repository as profiles_repository
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.committed import fresh_man

BLOCKED_WAIT_S = 3.0


async def _ready_but_the_photo(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    """A man at the selfie step with everything in place but his one photo,
    still being checked."""
    man = await fresh_man(engine)
    photo_id = uuid.uuid4()
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.SELFIE)
        )
        await session.execute(
            update(Profile)
            .where(Profile.user_id == man)
            .values(
                seeking=Seeking.WOMEN,
                first_name="Race",
                hometown="Jalandhar",
                city="Phagwara",
                location=profiles_repository.point(31.2139, 75.7680),
                username=f"race{uuid.uuid4().hex[:12]}",
                about="A profile waiting on its one photo, long enough to pass.",
            )
        )
        session.add(ProfileIntent(user_id=man, intent_id=1))
        session.add_all(
            ProfileInterest(user_id=man, interest_id=i) for i in range(1, 6)
        )
        session.add(
            Photo(
                id=photo_id,
                user_id=man,
                kind=PhotoKind.PUBLIC,
                position=0,
                raw_key=f"raw/{man}/{photo_id}",
            )
        )
    return man, photo_id


async def _never_onboarded_again(
    engine: AsyncEngine, man: uuid.UUID, photo_id: uuid.UUID
) -> None:
    """Back to what `fresh_man` made: at `dob`, an empty profile, no intents,
    interests or live photo. Moving off `done` is no move to it, so D-310's
    trigger takes it."""
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(delete(ProfileIntent).where(ProfileIntent.user_id == man))
        await session.execute(
            delete(ProfileInterest).where(ProfileInterest.user_id == man)
        )
        await session.execute(
            update(Profile)
            .where(Profile.user_id == man)
            .values(
                seeking=None,
                first_name=None,
                hometown=None,
                city=None,
                location=None,
                location_updated_at=None,
                username=None,
                about=None,
                completeness=0,
            )
        )
        await session.execute(
            update(Photo)
            .where(Photo.id == photo_id)
            .values(status=ReviewStatus.REJECTED, reject_reason="user_deleted")
        )
        await session.execute(
            update(User)
            .where(User.id == man)
            .values(onboarding_step=OnboardingStep.DOB)
        )


async def _waiting_on_a_lock(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        waiting = await connection.scalar(
            text(
                "select count(*) from pg_stat_activity "
                "where datname = current_database() and wait_event_type = 'Lock'"
            )
        )
    return int(waiting or 0)


async def test_finishing_waits_for_the_photos_decision(
    test_engine: AsyncEngine,
) -> None:
    man, photo_id = await _ready_but_the_photo(test_engine)

    async def finish() -> str:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await session.get(User, man)
            assert user is not None
            await session.commit()
            me = await service.complete(session, user)
        return me.onboarding_step.value

    try:
        async with AsyncSession(test_engine) as decision, decision.begin():
            # As moderation decides (T-4.4): the user's row first, then the photo.
            await users_service.locked_user(decision, man)
            await decision.execute(
                update(Photo)
                .where(Photo.id == photo_id)
                .values(status=ReviewStatus.APPROVED, public_key=f"p/{photo_id}.jpg")
            )
            finishing = asyncio.create_task(finish())
            blocked = 0
            for _ in range(int(BLOCKED_WAIT_S / 0.05)):
                blocked = await _waiting_on_a_lock(test_engine)
                if blocked or finishing.done():
                    break
                await asyncio.sleep(0.05)

        step = await finishing
        async with AsyncSession(test_engine) as session:
            completeness = await session.scalar(
                select(Profile.completeness).where(Profile.user_id == man)
            )
    finally:
        await _never_onboarded_again(test_engine, man, photo_id)

    assert blocked == 1  # the overlap was forced: the finish waited on the row
    assert step == "done"
    assert completeness == 50
