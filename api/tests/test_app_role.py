"""The app's database role (T-1.22, from P-18): read and write rows, nothing more.

Staging and production connect as a login role inside `velora_app`; migrations
run as the owner. These tests connect as a test login role in the same group
and prove the triggers' bypasses and the guarded writes are all refused.
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core.db import build_engine
from app.core.enums import Gender, LedgerReason
from app.core.security import normalize_phone
from app.modules.users import repository as users_repository
from app.modules.users import service as users_service
from app.modules.wallet import service as wallet_service
from app.modules.wallet.rules import Ref, RefType
from tests.conftest import make_test_settings
from tests.infra import TEST_DATABASE_URL

APP_ROLE = "velora_app"
# A login role in the local Postgres server, for these tests only. Roles belong
# to the server, not the database, so it outlives the run; creating it again is
# a no-op.
TEST_LOGIN = "velora_app_test"
TEST_PASSWORD = "velora_app_test"  # a local test role, not a secret

INSUFFICIENT_PRIVILEGE = "42501"


def _sqlstate(error: DBAPIError) -> str | None:
    orig = error.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def _refused(conn: AsyncConnection, statement: str) -> str:
    """Run `statement` in a savepoint, expect SQLSTATE 42501, return the message."""
    with pytest.raises(DBAPIError) as excinfo:
        async with conn.begin_nested():
            await conn.execute(text(statement))
    assert _sqlstate(excinfo.value) == INSUFFICIENT_PRIVILEGE, str(excinfo.value)
    return str(excinfo.value.orig)


@pytest.fixture(scope="module")
async def app_role_engine(test_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with test_engine.begin() as owner:
        await owner.execute(
            text(
                f"""
                do $$ begin
                    if not exists (select from pg_roles where rolname = '{TEST_LOGIN}') then
                        create role {TEST_LOGIN} login password '{TEST_PASSWORD}'
                            in role {APP_ROLE};
                    end if;
                end $$
                """
            )
        )
    url = make_url(TEST_DATABASE_URL).set(username=TEST_LOGIN, password=TEST_PASSWORD)
    engine = build_engine(url.render_as_string(hide_password=False))
    yield engine
    await engine.dispose()


@pytest.fixture
async def as_app(app_role_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection as the app role, inside a transaction that is rolled back."""
    async with app_role_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()


async def test_the_app_role_reads_and_writes_rows(as_app: AsyncConnection) -> None:
    await as_app.execute(
        text("insert into app_config (key, value) values ('test.app_role', '1'::jsonb)")
    )
    await as_app.execute(
        text("update app_config set value = '2'::jsonb where key = 'test.app_role'")
    )
    value = await as_app.scalar(
        text("select value from app_config where key = 'test.app_role'")
    )
    users = await as_app.scalar(text("select count(*) from users"))

    assert value == 2
    assert users is not None and users >= 0


@pytest.mark.parametrize(
    ("table", "statement"),
    [
        ("ledger_entries", "update ledger_entries set delta = delta where false"),
        ("ledger_entries", "delete from ledger_entries where false"),
        ("ledger_entries", "truncate ledger_entries"),
        ("audit_log", "update audit_log set action = action where false"),
        ("audit_log", "delete from audit_log where false"),
        ("audit_log", "truncate audit_log"),
        ("payments", "delete from payments where false"),
        ("payments", "truncate payments"),
        ("messages", "delete from messages where false"),
        ("reports", "delete from reports where false"),
    ],
)
async def test_guarded_writes_are_refused(
    as_app: AsyncConnection, table: str, statement: str
) -> None:
    assert f"permission denied for table {table}" in await _refused(as_app, statement)


async def test_payments_status_can_still_change(as_app: AsyncConnection) -> None:
    # 0 rows, but the privilege check passes: a payment's status moves.
    result = await as_app.execute(
        text("update payments set status = status where false")
    )
    assert result.rowcount == 0


async def test_the_app_role_can_delete_an_under_18_account(
    as_app: AsyncConnection,
) -> None:
    """D-072's deletion runs as the app role on staging and production: signup's
    rows, written and then deleted through the same repository calls the dob
    step makes, with only the number's hash kept (T-3.6)."""
    settings = make_test_settings()
    phone = normalize_phone("+919812345699")
    session = AsyncSession(bind=as_app, join_transaction_mode="create_savepoint")
    account = await users_service.create_account(session, phone, settings)
    user_id = account.user.id

    await users_repository.ban_phone_hash(session, account.user.phone_hash, "underage")
    await users_repository.delete_account(session, user_id)
    await session.flush()

    for table in ("users", "profiles", "wallets", "notification_prefs"):
        column = "id" if table == "users" else "user_id"
        left = await as_app.scalar(
            text(f"select count(*) from {table} where {column} = :id"),
            {"id": user_id},
        )
        assert left == 0, table
    kept = await as_app.scalar(
        text("select reason from banned_identities where value = :hash"),
        {"hash": account.user.phone_hash},
    )
    assert kept == "underage"


async def test_the_app_role_credits_and_debits_through_the_wallet(
    as_app: AsyncConnection,
) -> None:
    """Staging and production move money as the app role (T-5.1): the locked
    read, the balance, the ledger row and D-076's trigger all work under its
    privileges."""
    session = AsyncSession(bind=as_app, join_transaction_mode="create_savepoint")
    account = await users_service.create_account(
        session, normalize_phone("+919812345698"), make_test_settings()
    )
    account.user.gender = Gender.MALE
    await session.flush()
    man = account.user.id

    credited = await wallet_service.credit(
        session, man, 10, LedgerReason.ADMIN_GRANT, event="app-role"
    )
    debited = await wallet_service.debit(
        session, man, 4, LedgerReason.THREAD_OPEN, ref=Ref(RefType.THREAD, uuid.uuid4())
    )

    assert (credited.applied, debited.applied) == (True, True)
    assert debited.entry.balance_after == 6
    balance = await as_app.scalar(
        text("select balance from wallets where user_id = :u"), {"u": man}
    )
    rows = await as_app.scalar(
        text("select count(*) from ledger_entries where user_id = :u"), {"u": man}
    )
    assert (balance, rows) == (6, 2)


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        (
            "set session_replication_role = replica",
            "permission denied to set parameter",
        ),
        (
            "alter table ledger_entries disable trigger all",
            "must be owner of table ledger_entries",
        ),
        # D-076's guard, the one with legal weight, can't be switched off either.
        (
            "alter table wallets disable trigger wallets_only_men",
            "must be owner of table wallets",
        ),
        (
            "drop trigger ledger_entries_only_men on ledger_entries",
            "must be owner of relation ledger_entries",
        ),
        # D-310's: no woman reaches `done` without a matched selfie (D-008).
        (
            "alter table users disable trigger users_done_needs_a_match",
            "must be owner of table users",
        ),
        ("alter table users add column sneaky int", "must be owner of table users"),
        ("create table app_role_probe (id int)", "permission denied for schema public"),
        (
            "select * from alembic_version",
            "permission denied for table alembic_version",
        ),
    ],
)
async def test_bypasses_and_ddl_are_refused(
    as_app: AsyncConnection, statement: str, message: str
) -> None:
    assert message in await _refused(as_app, statement)


async def test_no_refuse_change_trigger_is_reachable_by_the_app_role(
    test_engine: AsyncEngine,
) -> None:
    """For every table a refuse_change() trigger guards, the app role lacks the
    privilege the trigger refuses — so a future append-only table whose migration
    forgets to revoke fails here."""
    async with test_engine.connect() as owner:
        rows = (
            await owner.execute(
                text(
                    """
                    select c.relname as table_name, t.tgtype
                    from pg_trigger t
                    join pg_class c on c.oid = t.tgrelid
                    join pg_proc p on p.oid = t.tgfoid
                    where p.proname = 'refuse_change' and not t.tgisinternal
                    """
                )
            )
        ).all()
        # pg_trigger.tgtype bits: 8 = DELETE, 16 = UPDATE, 32 = TRUNCATE.
        guarded = {
            (row.table_name, privilege)
            for row in rows
            for bit, privilege in ((8, "DELETE"), (16, "UPDATE"), (32, "TRUNCATE"))
            if row.tgtype & bit
        }
        reachable = [
            (table, privilege)
            for table, privilege in sorted(guarded)
            if (
                await owner.execute(
                    text("select has_table_privilege(:role, :table, :privilege)"),
                    {"role": APP_ROLE, "table": table, "privilege": privilege},
                )
            ).scalar_one()
        ]

    assert {table for table, _ in guarded} >= {
        "ledger_entries",
        "audit_log",
        "payments",
    }
    assert reachable == []


def _migration(filename: str) -> ModuleType:
    """Load a migration module by file name (the versions directory isn't a package)."""
    path = Path(__file__).parent.parent / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_extensions_schema_usage_is_granted_where_the_schema_exists(
    test_engine: AsyncEngine,
) -> None:
    """Supabase keeps extensions in an `extensions` schema; locally they're in
    public, so this builds Supabase's layout inside a transaction that is rolled
    back, and runs 67e81c6c203d's SQL against it (T-1.22)."""
    migration = _migration("20261001_67e81c6c203d_app_role_extensions_usage.py")
    usage = text("select has_schema_privilege(:role, 'extensions', 'USAGE')")

    async with test_engine.connect() as owner:
        transaction = await owner.begin()
        try:
            # No `extensions` schema (the local layout): the grant does nothing.
            await owner.execute(text(migration.GRANT_EXTENSIONS_USAGE))

            await owner.execute(text("create schema extensions"))
            assert await owner.scalar(usage, {"role": APP_ROLE}) is False

            await owner.execute(text(migration.GRANT_EXTENSIONS_USAGE))
            assert await owner.scalar(usage, {"role": APP_ROLE}) is True

            await owner.execute(text(migration.REVOKE_EXTENSIONS_USAGE))
            assert await owner.scalar(usage, {"role": APP_ROLE}) is False
        finally:
            await transaction.rollback()
