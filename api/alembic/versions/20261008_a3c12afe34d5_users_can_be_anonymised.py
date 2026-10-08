"""users can be anonymised

Revision ID: a3c12afe34d5
Revises: 9b4e0d2c7a15
Create Date: 2026-10-08 12:00:00.000000

T-9.6 (D-051, D-500): an account deleted 29 days ago is erased, and its `users`
row stays, because the ledger, payments, messages and reports still name it
(rule 12). What erasing needs from `users`:

- **`anonymised_at`**, when it happened. Once set it never changes and never
  clears (`users_anonymised_for_good`), and only a `deleted` row carries it
  (`ck_users_anonymised_is_deleted`): an erased account can't come back.
- **`phone_enc` empty exactly when erased** (`ck_users_phone_enc_until_anonymised`):
  the stored number goes, and nothing else may empty it.
- **`phone_hash` unique among live accounts only** (`uq_users_phone_hash_live`).
  The erased row keeps its hash, so a banned or reported number can't escape by
  deleting (D-051), and the number is free for a new account. `ix_users_phone_hash`
  finds every row a number ever had, the erased too (T-9.5's search).
- **dob may be cleared by the erasure, and by nothing else** (D-501): the
  immutability trigger allows dob to become null only in the update that sets
  `anonymised_at`, and an anonymised row holds no dob or PIN ever after
  (`ck_users_anonymised_is_empty`): the trigger's first-set rule would
  otherwise let a date be written back. Gender stays: D-076's trigger reads it,
  and it names no one.

**The downgrade refuses while any account is erased:** its number is gone, and
`phone_enc` can't be made required again over an empty one.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c12afe34d5"
down_revision: str | Sequence[str] | None = "9b4e0d2c7a15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# T-1.9's function, word for word, so the downgrade restores exactly it.
IDENTITY_IMMUTABLE_BEFORE = """
create or replace function users_identity_immutable() returns trigger
language plpgsql as $$
begin
    if old.gender is not null and new.gender is distinct from old.gender then
        raise exception 'users.gender is immutable once set'
            using errcode = 'check_violation';
    end if;
    if old.dob is not null and new.dob is distinct from old.dob then
        raise exception 'users.dob is immutable once set'
            using errcode = 'check_violation';
    end if;
    return new;
end;
$$
"""

# The one exception: dob to null in the update that anonymises the row. Not to
# another date, and never on a row already anonymised, which can't be updated
# into anything else anyway (below).
IDENTITY_IMMUTABLE = """
create or replace function users_identity_immutable() returns trigger
language plpgsql as $$
begin
    if old.gender is not null and new.gender is distinct from old.gender then
        raise exception 'users.gender is immutable once set'
            using errcode = 'check_violation';
    end if;
    if old.dob is not null and new.dob is distinct from old.dob
       and not (new.dob is null
                and old.anonymised_at is null
                and new.anonymised_at is not null) then
        raise exception 'users.dob is immutable once set'
            using errcode = 'check_violation';
    end if;
    return new;
end;
$$
"""

ANONYMISED_FOR_GOOD = """
create function users_anonymised_for_good() returns trigger
language plpgsql as $$
begin
    if old.anonymised_at is not null
       and new.anonymised_at is distinct from old.anonymised_at then
        raise exception 'users.anonymised_at never changes once set'
            using errcode = 'check_violation';
    end if;
    return new;
end;
$$
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("anonymised_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column("users", "phone_enc", existing_type=sa.LargeBinary(), nullable=True)
    op.create_check_constraint(
        op.f("ck_users_phone_enc_until_anonymised"),
        "users",
        "(phone_enc IS NULL) = (anonymised_at IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_users_anonymised_is_deleted"),
        "users",
        "anonymised_at IS NULL OR status = 'deleted'",
    )
    op.create_check_constraint(
        op.f("ck_users_anonymised_is_empty"),
        "users",
        "anonymised_at IS NULL OR (dob IS NULL AND pin_hash IS NULL)",
    )
    op.drop_constraint(op.f("uq_users_phone_hash"), "users", type_="unique")
    op.create_index(
        "uq_users_phone_hash_live",
        "users",
        ["phone_hash"],
        unique=True,
        postgresql_where=sa.text("anonymised_at IS NULL"),
    )
    op.create_index("ix_users_phone_hash", "users", ["phone_hash"])
    op.execute(sa.text(IDENTITY_IMMUTABLE))
    op.execute(sa.text(ANONYMISED_FOR_GOOD))
    op.execute(
        sa.text(
            "create trigger trg_users_anonymised_for_good "
            "before update on users for each row "
            "execute function users_anonymised_for_good()"
        )
    )


def downgrade() -> None:
    """Downgrade schema: refused while any account is anonymised."""
    erased = op.get_bind().scalar(
        sa.text("select count(*) from users where anonymised_at is not null")
    )
    if erased:
        raise RuntimeError(
            f"{erased} accounts are anonymised: their numbers are gone, so "
            "phone_enc can't be required again and their hashes can't be made "
            "unique beside the live accounts that reuse them (D-500)"
        )
    op.execute(sa.text("drop trigger trg_users_anonymised_for_good on users"))
    op.execute(sa.text("drop function users_anonymised_for_good()"))
    op.execute(sa.text(IDENTITY_IMMUTABLE_BEFORE))
    op.drop_index("ix_users_phone_hash", table_name="users")
    op.drop_index("uq_users_phone_hash_live", table_name="users")
    op.create_unique_constraint(op.f("uq_users_phone_hash"), "users", ["phone_hash"])
    op.drop_constraint(op.f("ck_users_anonymised_is_empty"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_anonymised_is_deleted"), "users", type_="check")
    op.drop_constraint(
        op.f("ck_users_phone_enc_until_anonymised"), "users", type_="check"
    )
    op.alter_column(
        "users", "phone_enc", existing_type=sa.LargeBinary(), nullable=False
    )
    op.drop_column("users", "anonymised_at")
