"""only men hold credits

Revision ID: 190d7bebf133
Revises: 97ddae55f597
Create Date: 2026-10-03 19:34:44.828941

Only men hold credits (D-076, T-5.1). The one invariant here whose failure is a
regulatory position, not a bug: a woman can buy nothing with credits, so any
that reach her are payment between people, which takes Velora outside RBI's
closed-system exemption. So the database enforces it, not only the service: a
migration, a repair script or an admin tool writing the ledger directly would
bypass a service check, and nothing would go red.

One function, two triggers:

- `ledger_entries_only_men`: before every insert into `ledger_entries`.
- `wallets_only_men`: before every insert or update of `wallets` that leaves a
  balance other than 0, whichever column changed, so a balance can't reach a
  woman by moving a wallet's `user_id` either.

Each refuses unless the user's gender is `male`. That is an allowlist: a user
with no gender yet is refused too, so nobody can be credited and then choose
female. T-1.9's trigger stops a gender changing once set; it doesn't stop a
first choice. A user who doesn't exist is refused as well. The refusal is
`check_violation` (23514) naming the trigger as its constraint, so a test can
tell which guard said no.

The triggers only see new writes, so the upgrade first counts what they would
have refused: ledger rows, and wallets with a balance, belonging to anyone but
a man. If either count isn't 0 it fails, saying what it found, rather than
guard a state it can't vouch for.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "190d7bebf133"
down_revision: str | Sequence[str] | None = "97ddae55f597"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REFUSE_UNLESS_MALE = """
create function refuse_credits_unless_male() returns trigger
language plpgsql as $$
begin
    if (select gender from users where id = new.user_id) is distinct from 'male' then
        raise exception 'only a man may hold credits (D-076)'
            using errcode = 'check_violation', constraint = tg_name;
    end if;
    return new;
end;
$$
"""

REQUIRE_NOTHING_HELD = """
do $$
declare
    ledger_rows bigint;
    wallets_holding bigint;
begin
    select count(*) into ledger_rows
        from ledger_entries l left join users u on u.id = l.user_id
        where u.gender is distinct from 'male';
    select count(*) into wallets_holding
        from wallets w left join users u on u.id = w.user_id
        where w.balance <> 0 and u.gender is distinct from 'male';
    if ledger_rows <> 0 or wallets_holding <> 0 then
        raise exception '%', format(
            'only a man may hold credits (D-076), but %s ledger rows and %s wallets '
            'with a balance belong to someone else. Find out how before anything '
            'else: this migration won''t guard a state it can''t vouch for.',
            ledger_rows, wallets_holding);
    end if;
end $$
"""

TRIGGERS = (
    # (trigger name, timing and events, table, condition)
    ("ledger_entries_only_men", "before insert", "ledger_entries", None),
    ("wallets_only_men", "before insert or update", "wallets", "new.balance <> 0"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text(REQUIRE_NOTHING_HELD))
    op.execute(sa.text(REFUSE_UNLESS_MALE))
    for name, when, table, condition in TRIGGERS:
        guard = f" when ({condition})" if condition else ""
        op.execute(
            sa.text(
                f"create trigger {name} {when} on {table} for each row{guard} "
                "execute function refuse_credits_unless_male()"
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    for name, _, table, _ in TRIGGERS:
        op.execute(sa.text(f"drop trigger {name} on {table}"))
    op.execute(sa.text("drop function refuse_credits_unless_male()"))
