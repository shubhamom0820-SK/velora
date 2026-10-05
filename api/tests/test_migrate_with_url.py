"""`scripts/migrate-with-url` believes the database, not Alembic (P-65).

The script runs for real, as both deploys run it, against scratch databases on
this run's server: one migrated from empty by the script itself, then a copy of
it for each case, broken the way the case says. A check that can't fail isn't a
check, so every refusal here starts from a database Alembic is content with.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from tests.infra import API_DIR, RUN_SLOT, SERVER_URL, requires_infra, run_alembic

pytestmark = requires_infra

SCRIPT = API_DIR.parent / "scripts" / "migrate-with-url"
SCRIPTS = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini")))
HEAD = SCRIPTS.get_current_head()

# Names of this run's own, so no other run's scratch databases are touched.
_SLOT = RUN_SLOT.number if RUN_SLOT is not None else 0
AT_HEAD = f"velora_slot{_SLOT}_migrate_head_test"
CASE = f"velora_slot{_SLOT}_migrate_case_test"


@dataclass(frozen=True)
class Run:
    code: int
    out: str
    err: str


def database_url(name: str) -> str:
    return make_url(SERVER_URL).set(database=name).render_as_string(hide_password=False)


def engine_for(name: str) -> AsyncEngine:
    return create_async_engine(database_url(name), poolclass=NullPool)


async def run_script(name: str) -> Run:
    # The deploy's migrate job has none of the app's settings, so neither does
    # this: only what uv needs, and the owner's URL.
    env = {
        key: value
        for key, value in os.environ.items()
        if key in ("PATH", "HOME") or key.startswith("UV_")
    }
    env["MIGRATION_DATABASE_URL"] = database_url(name)
    child = await asyncio.create_subprocess_exec(
        str(SCRIPT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(child.communicate(), timeout=120)
    assert child.returncode is not None
    return Run(child.returncode, out.decode(), err.decode())


async def admin(*statements: str) -> None:
    engine = create_async_engine(
        SERVER_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
async def first_run() -> AsyncIterator[Run]:
    """An empty database, migrated to head by the script: what every case copies."""
    await admin(
        f'drop database if exists "{AT_HEAD}" with (force)',
        f'create database "{AT_HEAD}"',
    )
    try:
        yield await run_script(AT_HEAD)
    finally:
        await admin(f'drop database if exists "{AT_HEAD}" with (force)')


@pytest.fixture
async def case(first_run: Run) -> AsyncIterator[AsyncEngine]:
    """A copy of the database at head, for one case to break."""
    assert first_run.code == 0, first_run.err
    await admin(
        f'drop database if exists "{CASE}" with (force)',
        f'create database "{CASE}" template "{AT_HEAD}"',
    )
    engine = engine_for(CASE)
    try:
        yield engine
    finally:
        await engine.dispose()
        await admin(f'drop database if exists "{CASE}" with (force)')


async def execute(engine: AsyncEngine, *statements: str) -> None:
    async with engine.begin() as connection:
        for statement in statements:
            await connection.execute(text(statement))


def test_the_repo_has_one_head() -> None:
    assert len(SCRIPTS.get_heads()) == 1


async def test_an_empty_database_is_migrated_and_read_back(first_run: Run) -> None:
    assert first_run.code == 0, first_run.err
    assert f"Running upgrade  -> {SCRIPTS.get_base()}" in first_run.err
    assert first_run.out == (
        f"migrate: alembic_version holds {HEAD}.\n"
        f"migrate: that is the repo's head, {HEAD}.\n"
        "migrate: trigger ledger_entries_only_men on ledger_entries: present and enabled.\n"
        "migrate: trigger wallets_only_men on wallets: present and enabled.\n"
        "migrate: trigger users_done_needs_a_match on users: present and enabled.\n"
        "migrate: index uq_ledger_entries_one_per_event on ledger_entries: "
        "present, unique and valid.\n"
    )
    # And the database says so on a connection of its own, after the script's
    # has closed: what it printed was committed, not merely seen.
    engine = engine_for(AT_HEAD)
    try:
        async with engine.connect() as connection:
            version = await connection.scalar(
                text("select version_num from alembic_version")
            )
    finally:
        await engine.dispose()
    assert version == HEAD


async def test_a_database_already_at_head_passes(case: AsyncEngine) -> None:
    """Most deploys: no new migration, and the same answer."""
    run = await run_script(CASE)

    assert run.code == 0, run.err
    assert "Running upgrade" not in run.err
    assert f"migrate: that is the repo's head, {HEAD}.\n" in run.out


async def test_a_version_the_upgrade_did_not_leave_is_refused(
    case: AsyncEngine,
) -> None:
    """Alembic runs the last migration and says so, and the database keeps its
    old version: the false green P-65 exists for, made real."""
    await run_alembic(case, command.downgrade, "-1")
    async with case.connect() as connection:
        before = await connection.scalar(
            text("select version_num from alembic_version")
        )
    await execute(
        case,
        "create function keep_the_old_version() returns trigger language plpgsql"
        " as $$ begin new.version_num := old.version_num; return new; end $$",
        "create trigger keep_the_old_version before update on alembic_version"
        " for each row execute function keep_the_old_version()",
    )

    run = await run_script(CASE)

    assert f"Running upgrade {before} -> {HEAD}" in run.err
    assert run.code == 1
    assert run.out == f"migrate: alembic_version holds {before}.\n"
    assert run.err.endswith(
        f"migrate: refused. alembic_version holds ['{before}']; "
        f"the repo's head is {HEAD}.\n"
    )


# D-076's migration, which builds the two triggers. It was the head when this
# test was written; T-5.2's migrations followed it, so "-1" from head no longer
# reaches it, and the case goes down to the revision before it instead.
D076 = "190d7bebf133"


async def test_a_head_stamped_without_its_migration_is_refused(
    case: AsyncEngine,
) -> None:
    """`alembic stamp head` on a database short of D-076's migration: the head
    matches, and the guards that migration and the later ones build aren't
    there (T-4.8's, D-310, among them)."""
    revision = SCRIPTS.get_revision(D076)
    assert revision is not None and isinstance(revision.down_revision, str)
    await run_alembic(case, command.downgrade, revision.down_revision)
    await execute(case, f"update alembic_version set version_num = '{HEAD}'")

    run = await run_script(CASE)

    assert run.code == 1
    assert f"migrate: that is the repo's head, {HEAD}.\n" in run.out
    assert run.err.endswith(
        "migrate: refused. trigger ledger_entries_only_men on ledger_entries is missing.\n"
        "migrate: refused. trigger wallets_only_men on wallets is missing.\n"
        "migrate: refused. trigger users_done_needs_a_match on users is missing.\n"
    )


TRIGGERS = [
    ("ledger_entries", "ledger_entries_only_men"),
    ("wallets", "wallets_only_men"),
    ("users", "users_done_needs_a_match"),
]


@pytest.mark.parametrize(("table", "trigger"), TRIGGERS)
@pytest.mark.parametrize(
    ("break_it", "refusal"),
    [
        ("drop trigger {trigger} on {table}", "is missing"),
        ("alter table {table} disable trigger {trigger}", "is disabled (tgenabled D)"),
        # Fires only under session_replication_role = replica: never for the app.
        (
            "alter table {table} enable replica trigger {trigger}",
            "is disabled (tgenabled R)",
        ),
    ],
    ids=["dropped", "disabled", "replica-only"],
)
async def test_a_trigger_that_refuses_nothing_is_refused(
    case: AsyncEngine, table: str, trigger: str, break_it: str, refusal: str
) -> None:
    await execute(case, break_it.format(table=table, trigger=trigger))

    run = await run_script(CASE)

    assert run.code == 1
    assert f"migrate: that is the repo's head, {HEAD}.\n" in run.out
    assert run.err.endswith(
        f"migrate: refused. trigger {trigger} on {table} {refusal}.\n"
    )


async def test_a_trigger_on_the_wrong_table_is_refused(case: AsyncEngine) -> None:
    """The right name on another table guards nothing of the table it names."""
    await execute(
        case,
        "drop trigger wallets_only_men on wallets",
        "create trigger wallets_only_men before insert on ledger_entries"
        " for each row execute function refuse_credits_unless_male()",
    )

    run = await run_script(CASE)

    assert run.code == 1
    assert run.err.endswith(
        "migrate: refused. trigger wallets_only_men on wallets is missing.\n"
    )


INDEX = "uq_ledger_entries_one_per_event"


@pytest.mark.parametrize(
    ("break_it", "refusal"),
    [
        ([f"drop index {INDEX}"], "is missing"),
        # The right name on another table vouches for nothing in the ledger.
        (
            [
                f"drop index {INDEX}",
                f"create unique index {INDEX} on wallets (user_id)",
            ],
            "is missing",
        ),
        (
            [f"drop index {INDEX}", f"create index {INDEX} on ledger_entries (id)"],
            "is not unique",
        ),
        # What a failed CREATE INDEX CONCURRENTLY leaves: an index Postgres won't
        # plan with, over rows that may already hold the duplicate that failed it.
        (
            [
                f"update pg_index set indisvalid = false where indexrelid = '{INDEX}'::regclass"
            ],
            "is not valid",
        ),
    ],
    ids=["dropped", "wrong-table", "not-unique", "invalid"],
)
async def test_an_index_that_isnt_unique_and_valid_is_refused(
    case: AsyncEngine, break_it: list[str], refusal: str
) -> None:
    await execute(case, *break_it)

    run = await run_script(CASE)

    assert run.code == 1
    assert f"migrate: that is the repo's head, {HEAD}.\n" in run.out
    assert run.err.endswith(
        f"migrate: refused. index {INDEX} on ledger_entries {refusal}.\n"
    )
