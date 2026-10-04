"""ledger shape names the new reasons

Revision ID: a1d7de534ef7
Revises: 4a7e20790605
Create Date: 2026-10-04 23:10:13.497068

D-077's shape for the two reasons the last migration added (D-251, T-5.2):

| reason          | direction | ref_type  | one entry per event?                     |
|-----------------|-----------|-----------|------------------------------------------|
| `thread_extend` | debit     | `thread`  | no: Extend repeats for one Thread (D-250) |
| `dm_message`    | debit     | `message` | yes: one charge per message               |

`ck_ledger_entries_reason_direction`, `ck_ledger_entries_reason_ref_type` and
`uq_ledger_entries_one_per_event` are each replaced by the same rule with the
two reasons in it. `ck_ledger_entries_ref_required` names only `admin_grant`,
so it doesn't change. From here these are the ledger's shape, not 97ddae55f597's
copies: `tests/break_guards.py` weakens this file to prove the tests see them.

The lists are written out, not imported from `wallet/rules.py`, because a
migration never changes after it merges (rule 11); `test_guards.py` proves the
database and RULES agree, reason by reason. The downgrade puts 97ddae55f597's
rules back, which no ledger row using either reason can pass: the CHECK refuses
to be re-created, and the migration before refuses on its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1d7de534ef7"
down_revision: str | Sequence[str] | None = "4a7e20790605"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREDITS = (
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
)
REPEATS_BEFORE = ("admin_grant", "thread_reopen")

DEBITS = (*DEBITS_BEFORE, "thread_extend", "dm_message")
REF_TYPES = (
    *REF_TYPES_BEFORE,
    ("thread_extend", "thread"),
    ("dm_message", "message"),
)
REPEATS = (*REPEATS_BEFORE, "thread_extend")

INDEX = "uq_ledger_entries_one_per_event"


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _direction(debits: Sequence[str]) -> str:
    return (
        f"(reason IN ({_sql_list(CREDITS)}) AND delta > 0) "
        f"OR (reason IN ({_sql_list(debits)}) AND delta < 0)"
    )


def _ref_type(ref_types: Sequence[tuple[str, str]]) -> str:
    return "ref_type IS NULL OR (reason, ref_type) IN ({})".format(
        ", ".join(f"('{reason}', '{ref_type}')" for reason, ref_type in ref_types)
    )


def _set_shape(
    debits: Sequence[str],
    ref_types: Sequence[tuple[str, str]],
    repeats: Sequence[str],
) -> None:
    op.drop_index(INDEX, table_name="ledger_entries")
    for name, condition in (
        ("reason_direction", _direction(debits)),
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
    _set_shape(DEBITS, REF_TYPES, REPEATS)


def downgrade() -> None:
    """Downgrade schema: 97ddae55f597's rules."""
    _set_shape(DEBITS_BEFORE, REF_TYPES_BEFORE, REPEATS_BEFORE)
