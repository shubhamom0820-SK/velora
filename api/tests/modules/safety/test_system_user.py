"""The system user (T-9.2, P-20, D-905): who `audit_log` names when nobody did
it. Created by migration 4800f0e8d5a9, shaped like an erased account: it can't
sign in, appears nowhere people are listed, refers nobody, and the erasure
skips it. The downgrade refuses while the audit log names it.

Alembic runs on the test's own connection, inside its transaction, so all of
it rolls back (as `test_migration.py` does)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core import clock
from app.core.enums import OnboardingStep, Role, UserStatus
from app.core.errors import AppError
from app.modules.account import repository as account_repository
from app.modules.admin.service import SYSTEM_USER_ID
from app.modules.referrals import rules as referral_rules
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import MakeUser
from tests.modules.discovery.support import bearer
from tests.modules.safety.test_migration import _alembic

pytestmark = pytest.mark.usefixtures("test_redis")

BEFORE = "086fa0402d0d"  # the system user (4800f0e8d5a9) comes just after


async def _system(db: AsyncSession) -> User | None:
    found: User | None = await db.scalar(
        select(User)
        .where(User.id == SYSTEM_USER_ID)
        .execution_options(populate_existing=True)
    )
    return found


async def test_the_migration_made_it_shaped_like_an_erased_account(
    db: AsyncSession,
) -> None:
    user = await _system(db)
    assert user is not None
    assert (user.status, user.role, user.onboarding_step) == (
        UserStatus.DELETED,
        Role.USER,
        OnboardingStep.DOB,
    )
    assert user.anonymised_at is not None
    assert (user.phone_enc, user.dob, user.pin_hash, user.gender) == (
        None,
        None,
        None,
        None,
    )
    # No HMAC is "system": no number can sign in to it.
    assert user.phone_hash == "system"


async def test_it_may_not_sign_in(db: AsyncSession) -> None:
    user = await _system(db)
    assert user is not None
    with pytest.raises(AppError) as refused:
        users_service.refuse_who_may_not_sign_in(user)
    assert refused.value.code == "SESSION_REVOKED"


async def test_it_refers_nobody(db: AsyncSession) -> None:
    user = await _system(db)
    assert user is not None
    assert user.referral_code == "system-user"
    assert not referral_rules.code_works(user.onboarding_step, user.status)


async def test_the_erasure_never_takes_it(db: AsyncSession) -> None:
    due = await account_repository.accounts_due_for_erasure(
        db, clock.now() + timedelta(days=3650)
    )
    assert SYSTEM_USER_ID not in due


async def test_it_appears_nowhere_people_are_listed(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, token = await make_user()
    response = await client.get(f"/v1/users/{SYSTEM_USER_ID}", headers=bearer(token))
    assert response.status_code == 404


async def test_the_downgrade_refuses_while_the_audit_log_names_it(
    db: AsyncSession,
) -> None:
    await db.execute(
        text("insert into audit_log (actor_id, action) values (:id, 'fraud.freeze')"),
        {"id": SYSTEM_USER_ID},
    )

    with pytest.raises(RuntimeError, match="audit_log names the system user"):
        await _alembic(db, command.downgrade, BEFORE)


async def test_down_and_up_again_with_nothing_naming_it(db: AsyncSession) -> None:
    await _alembic(db, command.downgrade, BEFORE)
    assert await _system(db) is None
    await _alembic(db, command.upgrade, "head")
    assert await _system(db) is not None
