"""What the database holds on its own, for a writer that skips
`onboarding.service` (a migration, a repair script, an admin tool, a later
task): `users_done_needs_a_match` (D-310, D-008). Only a man, or someone whose
selfie matched, moves to `done`; a row already there is left to P-161 and
P-163. Each refusal is identified by the trigger that made it, never by
SQLSTATE alone: T-1.9's identity trigger shares 23514."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.enums import Gender, OnboardingStep
from app.core.security import normalize_phone
from app.modules.users import service as users_service
from app.modules.users.models import User
from tests.conftest import make_test_settings
from tests.infra import API_DIR

TRIGGER = "users_done_needs_a_match"
# Every gender there is, and none: the allowlist must refuse a value added to
# the enum later as surely as it refuses no gender at all.
GENDERS: list[Gender | None] = [*Gender, None]

D310 = "15a9b138750b"  # the trigger's migration
BEFORE_D310 = "bc589ac265c2"


async def _person(db: AsyncSession, gender: Gender | None, *, verified: bool) -> User:
    """Signed up through signup's own service, at the selfie step."""
    phone = normalize_phone(f"+9196{secrets.randbelow(10**8):08d}")
    account = await users_service.create_account(db, phone, make_test_settings())
    await db.execute(
        text(
            "update users set gender = :g, is_verified = :v, "
            "onboarding_step = 'selfie' where id = :u"
        ),
        {
            "g": None if gender is None else gender.value,
            "v": verified,
            "u": account.user.id,
        },
    )
    return account.user


async def _attempt(db: AsyncSession, sql: str, params: dict[str, Any]) -> str | None:
    """Run `sql` in a savepoint: None if the database took it, otherwise the
    constraint that refused it (or the SQLSTATE, if none was named)."""
    try:
        async with db.begin_nested():
            await db.execute(text(sql), params)
    except IntegrityError as error:
        cause = error.orig.__cause__ if error.orig is not None else None
        name = getattr(cause, "constraint_name", None)
        return str(name or getattr(cause, "sqlstate", "unnamed"))
    return None


FINISH = "update users set onboarding_step = 'done' where id = :u"


@pytest.mark.critical  # 06-TESTING.md #8b
async def test_only_a_man_moves_to_done_unmatched(db: AsyncSession) -> None:
    refusals = {
        gender: await _attempt(
            db, FINISH, {"u": (await _person(db, gender, verified=False)).id}
        )
        for gender in GENDERS
    }

    assert {g for g, refused in refusals.items() if refused is None} == {Gender.MALE}
    assert {r for g, r in refusals.items() if g is not Gender.MALE} == {TRIGGER}


async def test_anyone_whose_selfie_matched_moves_to_done(db: AsyncSession) -> None:
    for gender in GENDERS:
        user = await _person(db, gender, verified=True)
        assert await _attempt(db, FINISH, {"u": user.id}) is None


@pytest.mark.critical  # 06-TESTING.md #8b: an insert is a move to `done` too
async def test_a_row_written_as_done_is_held_to_the_same_rule(db: AsyncSession) -> None:
    def row(gender: str, verified: bool) -> dict[str, Any]:
        tag = uuid.uuid4().hex[:12]
        return {
            "hash": f"hash-{tag}",
            "code": f"ref{tag}",
            "g": gender,
            "v": verified,
        }

    insert = (
        "insert into users (phone_hash, phone_enc, referral_code, gender, "
        "is_verified, onboarding_step) "
        "values (:hash, '\\x00', :code, :g, :v, 'done')"
    )

    assert await _attempt(db, insert, row("female", False)) == TRIGGER
    assert await _attempt(db, insert, row("female", True)) is None
    assert await _attempt(db, insert, row("male", False)) is None


async def test_a_row_already_done_is_left_to_p161_and_p163(db: AsyncSession) -> None:
    """Clearing a live woman's match is theirs to decide, so the guard checks
    only the move to `done`: her match cleared, and her step written again,
    are both taken."""
    woman = await _person(db, Gender.FEMALE, verified=True)
    assert await _attempt(db, FINISH, {"u": woman.id}) is None

    cleared = "update users set is_verified = false where id = :u"
    assert await _attempt(db, cleared, {"u": woman.id}) is None
    assert await _attempt(db, FINISH, {"u": woman.id}) is None


async def test_the_app_is_refused_by_the_trigger_itself(db: AsyncSession) -> None:
    """Through the ORM, as a careless service would write it: the trigger's
    own refusal, with its message."""
    woman = await _person(db, Gender.FEMALE, verified=False)
    await db.refresh(woman)
    woman.onboarding_step = OnboardingStep.DONE

    with pytest.raises(
        IntegrityError, match=r"only a man may finish without a matched"
    ):
        async with db.begin_nested():
            await db.flush()


# The migration asserts what the trigger can't see: rows from before it.


async def _alembic(db: AsyncSession, run: Callable[..., object], revision: str) -> None:
    """Run an Alembic command on the test's own connection, inside its
    transaction: Alembic sees one already open and leaves it to us."""
    connection = await db.connection()

    def _run(sync_connection: Connection) -> None:
        config = Config(str(API_DIR / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        run(config, revision)

    await connection.run_sync(_run)


@pytest.mark.critical  # 06-TESTING.md #8b
async def test_the_migration_refuses_to_guard_a_woman_already_done_unmatched(
    db: AsyncSession,
) -> None:
    """Back to before the trigger, a woman moved to `done` unmatched, then
    forward: the upgrade fails saying what it found. Rolled back, trigger and
    all."""
    woman = await _person(db, Gender.FEMALE, verified=False)

    with pytest.raises(DBAPIError) as refused:
        async with db.begin_nested():
            await _alembic(db, command.downgrade, BEFORE_D310)
            assert await _attempt(db, FINISH, {"u": woman.id}) is None
            await _alembic(db, command.upgrade, D310)

    assert (
        "only a man may finish without a matched selfie (D-008), but 1 users are "
        "done, not men and not verified"
    ) in str(refused.value)
    triggers = await db.scalar(
        text("select count(*) from pg_trigger where tgname = :name"), {"name": TRIGGER}
    )
    assert triggers == 1  # the downgrade was rolled back with the rest
