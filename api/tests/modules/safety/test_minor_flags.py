"""Repeated possible-minor flags go to a human (P-72, D-991, D-994, D-1050).

The flag that puts a person on the admins' list (two in 30 days, or two since
an admin's decision on them) tells every active admin: an in-app row, and a
push where they subscribe. Later flags while they still wait bring each
admin's row up to date and push nothing. Nothing here acts on the person.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.enums import Gender, Role, UserStatus
from app.modules.admin.models import AuditLogEntry
from app.modules.safety import fraud
from app.modules.safety import service as safety_service
from app.modules.safety.models import FraudEvent
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.notifications.support import in_app, outbox, subscribed


async def _admin(make_user: MakeUser, role: Role = Role.ADMIN) -> User:
    person, _ = await make_user(Gender.FEMALE)
    person.role = role
    return person


async def _flag(db: AsyncSession, user: User, score: float, at: datetime) -> None:
    """A flag as `photos.service` records one, dated `at`, then escalated."""
    db.add(
        FraudEvent(
            user_id=user.id,
            signal=fraud.POSSIBLE_MINOR_SCORE,
            weight=safety_service.POSSIBLE_MINOR_WEIGHT,
            meta={"what": safety_service.POSSIBLE_MINOR_NOTE, "score": score},
            created_at=at,
        )
    )
    await db.flush()
    await safety_service.escalate_possible_minor(db, user.id)


def _ago(days: float) -> datetime:
    return clock.now() - timedelta(days=days)


async def test_one_flag_tells_nobody(db: AsyncSession, make_user: MakeUser) -> None:
    admin = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)

    await _flag(db, woman, 0.5, _ago(1))

    assert await in_app(db, admin.id) == []


async def test_the_second_flag_in_30_days_tells_every_active_admin_alone(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin = await _admin(make_user)
    await subscribed(db, admin.id)
    moderator = await _admin(make_user, Role.MODERATOR)
    woman, _ = await make_user(Gender.FEMALE)
    first, second = _ago(29), _ago(0.5)

    await _flag(db, woman, 0.41, first)
    await _flag(db, woman, 0.93, second)

    payload = {
        "subject_id": str(woman.id),
        "flags": 2,
        "scores": [0.41, 0.93],
        "first_at": first.isoformat(),
        "last_at": second.isoformat(),
    }
    assert await in_app(db, admin.id) == [("minor_flags", payload)]
    assert await outbox(db, admin.id) == [("minor_flags", payload)]
    assert await in_app(db, moderator.id) == []
    # The person is told nothing, and nothing is done to her (D-093).
    assert await in_app(db, woman.id) == []
    await db.refresh(woman)
    assert woman.status is UserStatus.ACTIVE


async def test_two_flags_more_than_30_days_apart_tell_nobody(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)

    await _flag(db, woman, 0.5, _ago(31))
    await _flag(db, woman, 0.5, _ago(0.5))

    assert await in_app(db, admin.id) == []


async def test_a_third_flag_before_review_sends_no_second_push(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """The founder's change to the plan: told once on entering the list; a
    later flag updates the row's count and times, and pushes nothing."""
    admin = await _admin(make_user)
    await subscribed(db, admin.id)
    woman, _ = await make_user(Gender.FEMALE)
    first, second, third = _ago(10), _ago(5), _ago(0.5)
    await _flag(db, woman, 0.41, first)
    await _flag(db, woman, 0.52, second)
    [pushed] = await outbox(db, admin.id)

    await _flag(db, woman, 0.93, third)

    assert await outbox(db, admin.id) == [pushed]
    assert await in_app(db, admin.id) == [
        (
            "minor_flags",
            {
                "subject_id": str(woman.id),
                "flags": 3,
                "scores": [0.41, 0.52, 0.93],
                "first_at": first.isoformat(),
                "last_at": third.isoformat(),
            },
        )
    ]


async def test_after_a_decision_only_two_new_flags_bring_them_back(
    db: AsyncSession, make_user: MakeUser
) -> None:
    """D-1050: the flags before the decision no longer count, so one more
    photo doesn't reopen a settled review; two new ones do, told again."""
    admin = await _admin(make_user)
    await subscribed(db, admin.id)
    woman, _ = await make_user(Gender.FEMALE)
    await _flag(db, woman, 0.41, _ago(20))
    await _flag(db, woman, 0.52, _ago(19))
    db.add(
        AuditLogEntry(
            actor_id=admin.id,
            action=fraud.MINOR_REVIEWED,
            target_type="user",
            target_id=woman.id,
            meta={"decision": "adult"},
            created_at=_ago(18),
        )
    )
    await db.flush()
    assert len(await outbox(db, admin.id)) == 1

    await _flag(db, woman, 0.6, _ago(2))
    assert len(await outbox(db, admin.id)) == 1
    assert await safety_service.minor_flags_awaiting(db, woman.id) is None

    await _flag(db, woman, 0.7, _ago(1))
    assert len(await outbox(db, admin.id)) == 2
    # A new row: the first review's stays as it was.
    counts = sorted((p["flags"], p["scores"]) for _, p in await in_app(db, admin.id))
    assert counts == [(2, [0.41, 0.52]), (2, [0.6, 0.7])]


async def test_someone_elses_flags_never_count_toward_hers(
    db: AsyncSession, make_user: MakeUser
) -> None:
    admin = await _admin(make_user)
    woman, _ = await make_user(Gender.FEMALE)
    other, _ = await make_user(Gender.FEMALE)
    await _flag(db, other, 0.5, _ago(3))

    await _flag(db, woman, 0.5, _ago(1))

    assert await in_app(db, admin.id) == []
