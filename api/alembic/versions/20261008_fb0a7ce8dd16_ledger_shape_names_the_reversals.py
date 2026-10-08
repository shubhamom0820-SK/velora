"""ledger shape names the reversals

Revision ID: fb0a7ce8dd16
Revises: e9a09934aeb7
Create Date: 2026-10-08 18:00:01.000000

D-077's shape for the two reasons the last migration added (T-8.2, D-521):

| reason              | direction | ref_type  | one entry per event?                          |
|---------------------|-----------|-----------|-----------------------------------------------|
| `purchase_reversal` | debit     | `payment` | no: one per refund or dispute, named by its id |
| `purchase_restored` | credit    | `payment` | no: one per refund or dispute, named by its id |

A payment may be refunded in parts, or refunded and disputed, so each repeats
for one payment, as `thread_extend` does for one Thread: the caller names the
event, the refund's or dispute's own Razorpay id (`rfnd_…`, `disp_…`), and the
key holds one entry per refund or dispute.

`ck_ledger_entries_reason_direction`, `ck_ledger_entries_reason_ref_type` and
`uq_ledger_entries_one_per_event` are each replaced by the same rule with the
two reasons in it, as a1d7de534ef7 did for T-5.2's. `ck_ledger_entries_ref_required`
names only `admin_grant`, so it doesn't change. From here these are the
ledger's shape: `tests/break_guards.py` weakens this file.

The lists are written out, never imported from `wallet/rules.py` (rule 11);
`test_guards.py` proves the database and RULES agree, reason by reason. The
downgrade puts a1d7de534ef7's rules back, which no ledger row using either
reason can pass: the CHECK refuses to be re-created, and the migration before
refuses on its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb0a7ce8dd16"
down_revision: str | Sequence[str] | None = "e9a09934aeb7"
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
)
REPEATS_BEFORE = ("admin_grant", "thread_reopen", "thread_extend")

CREDITS = (*CREDITS_BEFORE, "purchase_restored")
DEBITS = (*DEBITS_BEFORE, "purchase_reversal")
REF_TYPES = (
    *REF_TYPES_BEFORE,
    ("purchase_reversal", "payment"),
    ("purchase_restored", "payment"),
)
REPEATS = (*REPEATS_BEFORE, "purchase_reversal", "purchase_restored")

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
    # NOT IN, as before: a reason added later is one per event until a
    # migration says it may repeat.
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
    """Downgrade schema: a1d7de534ef7's rules."""
    _set_shape(CREDITS_BEFORE, DEBITS_BEFORE, REF_TYPES_BEFORE, REPEATS_BEFORE)
