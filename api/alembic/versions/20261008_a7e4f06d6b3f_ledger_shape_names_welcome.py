"""ledger shape names welcome

Revision ID: a7e4f06d6b3f
Revises: acfda05a9f20
Create Date: 2026-10-08 20:00:01.000000

D-077's shape for the reason the last migration added (T-8.11, D-470):

| reason    | direction | ref_type | one entry per event?                         |
|-----------|-----------|----------|----------------------------------------------|
| `welcome` | credit    | `user`   | yes: the man himself is the event, so one ever |

Its ref is the man himself, so its key is `{user_id}:welcome:{user_id}`, and
the per-event index holds one account to one grant however the key is built. A
second account on the same number is a new `user_id`, which the ledger can't
see: `welcome_grants`, the next migration, stops that.

`ck_ledger_entries_reason_direction` and `ck_ledger_entries_reason_ref_type`
are each replaced by the same rule with `welcome` in it, as fb0a7ce8dd16 did for
T-8.2's. `uq_ledger_entries_one_per_event` is re-created unchanged: its list is
of the reasons that repeat, `NOT IN`, so `welcome` is inside it already, and is
named here only so the downgrade puts back exactly what stood.
`ck_ledger_entries_ref_required` names only `admin_grant`, so it doesn't change.
From here these are the ledger's shape: `tests/break_guards.py` weakens this file.

The lists are written out, never imported from `wallet/rules.py` (rule 11);
`test_guards.py` proves the database and RULES agree, reason by reason. The
downgrade puts fb0a7ce8dd16's rules back, which no ledger row using `welcome`
can pass: the CHECK refuses to be re-created, and the migration before refuses
on its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7e4f06d6b3f"
down_revision: str | Sequence[str] | None = "acfda05a9f20"
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
)
REPEATS = (
    "admin_grant",
    "thread_reopen",
    "thread_extend",
    "purchase_reversal",
    "purchase_restored",
)

CREDITS = (*CREDITS_BEFORE, "welcome")
DEBITS = DEBITS_BEFORE
REF_TYPES = (*REF_TYPES_BEFORE, ("welcome", "user"))

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
    # NOT IN, as before: `welcome` is one per event, as every reason is until
    # a migration says it may repeat.
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
    """Downgrade schema: fb0a7ce8dd16's rules."""
    _set_shape(CREDITS_BEFORE, DEBITS_BEFORE, REF_TYPES_BEFORE, REPEATS)
