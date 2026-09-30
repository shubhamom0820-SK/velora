"""app role

Revision ID: 4e87b5ba8780
Revises: c4193b88d395
Create Date: 2026-09-30 21:08:13.238735

The least-privileged role the API and worker connect as (T-1.22, from P-18).

`velora_app` is a NOLOGIN group role. Each environment creates its own login role
inside it, with a password, outside git (infra/STAGING.md); migrations keep
running as the owner. The app reads and writes rows, and nothing more:

- It owns nothing, so it can't ALTER a table or DISABLE TRIGGER, and it can't
  SET session_replication_role (superuser only) — the two ways past the
  refuse_change() triggers of T-1.12 and T-1.13. No TRUNCATE anywhere.
- ledger_entries and audit_log: SELECT and INSERT only (append-only).
- payments, messages and reports: no DELETE (CLAUDE.md rule 12). payments keeps
  UPDATE: its status moves.
- alembic_version: nothing. PostGIS's spatial_ref_sys, where it's in public
  (locally): SELECT only.

Tables created by later migrations get SELECT, INSERT, UPDATE and DELETE by
default. A new append-only or never-deleted table's migration must revoke what
the app shouldn't have: tests/test_app_role.py fails for any table whose
refuse_change() trigger the app role could reach.

On Supabase, `anon` and `authenticated` lose every privilege on our tables too:
its Data API would otherwise serve each table in `public` to anyone holding the
project's anon key, which Supabase treats as public. Those roles don't exist
locally, so that step does nothing here.

Roles belong to the whole Postgres server, not one database, so downgrade()
revokes this database's privileges and leaves the role. It doesn't give `anon`
and `authenticated` their privileges back.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e87b5ba8780"
down_revision: str | Sequence[str] | None = "c4193b88d395"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "velora_app"
APPEND_ONLY = ("ledger_entries", "audit_log")
NEVER_DELETED = ("payments", "messages", "reports")
SUPABASE_API_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"""
        do $$ begin
            if not exists (select from pg_roles where rolname = '{APP_ROLE}') then
                create role {APP_ROLE} nologin;
            end if;
        end $$
        """
    )
    op.execute(f"grant usage on schema public to {APP_ROLE}")
    op.execute(
        f"grant select, insert, update, delete on all tables in schema public to {APP_ROLE}"
    )
    op.execute(f"grant usage, select on all sequences in schema public to {APP_ROLE}")
    op.execute(f"revoke all on alembic_version from {APP_ROLE}")
    for table in APPEND_ONLY:
        op.execute(f"revoke update, delete on {table} from {APP_ROLE}")
    for table in NEVER_DELETED:
        op.execute(f"revoke delete on {table} from {APP_ROLE}")
    op.execute(
        f"""
        do $$ begin
            if to_regclass('public.spatial_ref_sys') is not null then
                revoke insert, update, delete on public.spatial_ref_sys from {APP_ROLE};
            end if;
        end $$
        """
    )

    # Tables and sequences created by later migrations (run as this same owner).
    op.execute(
        f"alter default privileges in schema public "
        f"grant select, insert, update, delete on tables to {APP_ROLE}"
    )
    op.execute(
        f"alter default privileges in schema public "
        f"grant usage, select on sequences to {APP_ROLE}"
    )

    # Supabase's Data API roles: nothing of ours, now or later.
    roles = ", ".join(f"'{role}'" for role in SUPABASE_API_ROLES)
    op.execute(
        f"""
        do $$
        declare r text;
        begin
            foreach r in array array[{roles}] loop
                if exists (select from pg_roles where rolname = r) then
                    execute format('revoke all on all tables in schema public from %I', r);
                    execute format('revoke all on all sequences in schema public from %I', r);
                    execute format('revoke all on all functions in schema public from %I', r);
                    execute format(
                        'alter default privileges in schema public revoke all on tables from %I', r);
                    execute format(
                        'alter default privileges in schema public revoke all on sequences from %I', r);
                    execute format(
                        'alter default privileges in schema public revoke all on functions from %I', r);
                end if;
            end loop;
        end $$
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        f"""
        do $$ begin
            if exists (select from pg_roles where rolname = '{APP_ROLE}') then
                alter default privileges in schema public revoke all on tables from {APP_ROLE};
                alter default privileges in schema public revoke all on sequences from {APP_ROLE};
                revoke all on all tables in schema public from {APP_ROLE};
                revoke all on all sequences in schema public from {APP_ROLE};
                revoke usage on schema public from {APP_ROLE};
            end if;
        end $$
        """
    )
