"""app role extensions usage

Revision ID: 67e81c6c203d
Revises: 4e87b5ba8780
Create Date: 2026-10-01

`velora_app` gets USAGE on the `extensions` schema, where there is one (T-1.22).

Supabase installs postgis, pg_trgm and citext in `extensions`, not `public`, and
a role we create has no USAGE there. Without it the app can't use a `citext`
or `geography` column's operators, or call PostGIS at all — found on staging
itself: `velora_api` could sign in but not call `postgis_lib_version()`.

Locally and in CI the extensions live in `public`, which 4e87b5ba8780 already
granted, so this does nothing there — and our local tests could never have seen
the gap (06-TESTING: a step is verified only where it runs). The runbook's role
check (infra/STAGING.md) proves it on Supabase.

Functions and types default to EXECUTE and USAGE for PUBLIC, so schema USAGE is
all the app needs.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "67e81c6c203d"
down_revision: str | Sequence[str] | None = "4e87b5ba8780"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANT_EXTENSIONS_USAGE = """
do $$ begin
    if exists (select from pg_namespace where nspname = 'extensions') then
        grant usage on schema extensions to velora_app;
    end if;
end $$
"""

REVOKE_EXTENSIONS_USAGE = """
do $$ begin
    if exists (select from pg_namespace where nspname = 'extensions')
        and exists (select from pg_roles where rolname = 'velora_app') then
        revoke usage on schema extensions from velora_app;
    end if;
end $$
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(GRANT_EXTENSIONS_USAGE)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(REVOKE_EXTENSIONS_USAGE)
