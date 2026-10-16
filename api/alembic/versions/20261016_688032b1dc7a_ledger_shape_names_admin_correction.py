"""ledger shape names admin correction

Revision ID: 688032b1dc7a
Revises: eb2e5b3a5cc8
Create Date: 2026-10-16 09:00:01.000000

D-077's shape for the reason the last migration added (T-9.5, D-923):

| reason             | direction | ref_type    | one entry per event?                   |
|--------------------|-----------|-------------|----------------------------------------|
| `admin_correction` | debit     | `audit_log` | no: it repeats, as `admin_grant` does  |

An admin's correction names the `audit_log` row its call writes, as an admin's
grant does from the next migration, and its event is the admin's
`Idempotency-Key`, so the per-event index leaves it out, as it leaves out
`admin_grant` (the founder's answer in T-9.5's brief). Each call writes a new
audit row, so the ref is one per correction anyway.

`ck_ledger_entries_reason_direction` and `ck_ledger_entries_reason_ref_type`
are each replaced by the same rule with `admin_correction` in it, as
a7e4f06d6b3f did for `welcome`, and `uq_ledger_entries_one_per_event` is
re-created with it among the reasons that repeat. `ck_ledger_entries_ref_required`
is the next migration's. From here these are the ledger's shape:
`tests/break_guards.py` weakens this file.

The lists are written out, never imported from `wallet/rules.py` (rule 11);
`test_guards.py` proves the database and RULES agree, reason by reason. The
downgrade puts a7e4f06d6b3f's rules back, which no ledger row using
`admin_correction` can pass: the CHECK refuses to be re-created, and the
migration before refuses on its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "688032b1dc7a"
down_revision: str | Sequence[str] | None = "eb2e5b3a5cc8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREDITS_BEFORE = (
    "purchase",
    "purchase_bonus",
    "referral_reward",
    "admin_grant",
    "refund",
    "refund_banned_partner",
    "refund_album_declined",
    "purchase_restored",
    "welcome",
)
DEBITS_BEFORE = (
    "gift",
    "thread_open",
    "dm_open",
    "thread_reopen",
    "voice_unlock",
    "album_request",
    "super_like",
    "liked_you_reveal",
    "thread_extend",
    "dm_message",
    "purchase_reversal",
)
REF_TYPES_BEFORE = (
    ("purchase", "payment"),
    ("purchase_bonus", "payment"),
    ("referral_reward", "referral"),
    ("admin_grant", "audit_log"),
    ("refund", "ledger_entry"),
    ("refund_banned_partner", "ledger_entry"),
    ("refund_album_declined", "album_request"),
    ("gift", "gift_send"),
    ("thread_open", "thread"),
    ("dm_open", "thread"),
    ("thread_reopen", "thread"),
    ("voice_unlock", "message"),
    ("album_request", "album_request"),
    ("super_like", "user"),
    ("liked_you_reveal", "user"),
    ("thread_extend", "thread"),
    ("dm_message", "message"),
    ("purchase_reversal", "payment"),
    ("purchase_restored", "payment"),
    ("welcome", "user"),
)
REPEATS_BEFORE = (
    "admin_grant",
    "thread_reopen",
    "thread_extend",
    "purchase_reversal",
    "purchase_restored",
)

CREDITS = CREDITS_BEFORE
DEBITS = (*DEBITS_BEFORE, "admin_correction")
REF_TYPES = (*REF_TYPES_BEFORE, ("admin_correction", "audit_log"))
REPEATS = (*REPEATS_BEFORE, "admin_correction")

INDEX = "uq_ledger_entries_one_per_event"


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _direction(credits: Sequence[str], debits: Sequence[str]) -> str:
    return (
        f"(reason IN ({_sql_list(credits)}) AND delta > 0) "
        f"OR (reason IN ({_sql_list(debits)}) AND delta < 0)"
    )


def _ref_type(ref_types: Sequence[tuple[str, str]]) -> str:
    return "ref_type IS NULL OR (reason, ref_type) IN ({})".format(
        ", ".join(f"('{reason}', '{ref_type}')" for reason, ref_type in ref_types)
    )


def _set_shape(
    credits: Sequence[str],
    debits: Sequence[str],
    ref_types: Sequence[tuple[str, str]],
    repeats: Sequence[str],
) -> None:
    op.drop_index(INDEX, table_name="ledger_entries")
    for name, condition in (
        ("reason_direction", _direction(credits, debits)),
        ("reason_ref_type", _ref_type(ref_types)),
    ):
        op.drop_constraint(op.f(f"ck_ledger_entries_{name}"), "ledger_entries")
        op.create_check_constraint(
            op.f(f"ck_ledger_entries_{name}"), "ledger_entries", condition
        )
    op.create_index(
        INDEX,
        "ledger_entries",
        ["user_id", "reason", "ref_type", "ref_id"],
        unique=True,
        postgresql_where=sa.text(f"reason NOT IN ({_sql_list(repeats)})"),
    )


def upgrade() -> None:
    """Upgrade schema."""
    _set_shape(CREDITS, DEBITS, REF_TYPES, REPEATS)


def downgrade() -> None:
    """Downgrade schema: a7e4f06d6b3f's rules."""
    _set_shape(CREDITS_BEFORE, DEBITS_BEFORE, REF_TYPES_BEFORE, REPEATS_BEFORE)
