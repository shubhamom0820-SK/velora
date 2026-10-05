"""a woman finishes only with a matched selfie

Revision ID: 15a9b138750b
Revises: bc589ac265c2
Create Date: 2026-10-05 16:38:26.000450

A woman's profile never goes live without a selfie that matched her photos
(D-008, T-4.8, D-310). `onboarding.service.complete()` checks it, and this
makes it impossible in the database too: a migration, a repair script, an
admin tool or a later task writing `users` directly would bypass the service,
and nothing would go red. Built in this task at the direction of the advisor
directing T-4.8 (Claude, in a separate chat), relayed by the founder, 5 October
2026 (D-310).

`users_done_needs_a_match`, before every insert, and every update of
`onboarding_step`, that leaves the step `done`: refused unless the user is a
man or `is_verified`. That is an allowlist, as the service's is: a user with
no gender is refused too. Only the move to `done` is checked, never a row
already there: what happens to a live woman whose match is later undone is
P-161's and P-163's to decide, and this doesn't decide it for them. The
refusal is `check_violation` (23514) naming the trigger as its constraint, as
D-076's are, so a test can tell which guard said no.

The trigger only sees new writes, so the upgrade first counts the rows it
would have refused: anyone `done`, not a man and not verified. If that isn't 0
it fails, saying what it found, rather than guard a state it can't vouch for.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15a9b138750b"
down_revision: str | Sequence[str] | None = "bc589ac265c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REFUSE_DONE_WITHOUT_A_MATCH = """
create function refuse_done_without_a_match() returns trigger
language plpgsql as $$
begin
    if tg_op = 'UPDATE' and old.onboarding_step = 'done' then
        return new;
    end if;
    if new.gender is distinct from 'male' and not new.is_verified then
        raise exception 'only a man may finish without a matched selfie (D-008)'
            using errcode = 'check_violation', constraint = tg_name;
    end if;
    return new;
end;
$$
"""

REQUIRE_NONE_DONE_WITHOUT_A_MATCH = """
do $$
declare
    unmatched bigint;
begin
    select count(*) into unmatched
        from users
        where onboarding_step = 'done'
          and gender is distinct from 'male'
          and not is_verified;
    if unmatched <> 0 then
        raise exception '%', format(
            'only a man may finish without a matched selfie (D-008), but %s users '
            'are done, not men and not verified. Find out how before anything '
            'else: this migration won''t guard a state it can''t vouch for.',
            unmatched);
    end if;
end $$
"""

TRIGGER = (
    "create trigger users_done_needs_a_match "
    "before insert or update of onboarding_step on users "
    "for each row when (new.onboarding_step = 'done') "
    "execute function refuse_done_without_a_match()"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text(REQUIRE_NONE_DONE_WITHOUT_A_MATCH))
    op.execute(sa.text(REFUSE_DONE_WITHOUT_A_MATCH))
    op.execute(sa.text(TRIGGER))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("drop trigger users_done_needs_a_match on users"))
    op.execute(sa.text("drop function refuse_done_without_a_match()"))
