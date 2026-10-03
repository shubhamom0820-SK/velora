"""ledger shape

Revision ID: 97ddae55f597
Revises: 684b79a19e8b
Create Date: 2026-10-03 19:34:43.540603

The ledger's shape (D-077, T-5.1): what makes a double credit impossible in the
database itself, not only in `wallet.service`.

- `ck_ledger_entries_reason_direction`: each reason has one direction, and
  `gift` is a debit (D-076). Both lists are allowlists, so a reason added to
  `ledger_reason_t` later can't be written until its migration names it here.
- `ck_ledger_entries_ref_required`: every reason but `admin_grant` names the
  row that justifies it.
- `ck_ledger_entries_reason_ref_type`: each reason has exactly one `ref_type`,
  because the index below is only as good as `ref_type` being right. A reason
  not listed can carry no ref at all, so it fails closed too.
- `uq_ledger_entries_one_per_event`: one entry per event, even if a key is
  built wrong. It leaves out the two reasons that legitimately repeat for one
  ref, `admin_grant` and `thread_reopen`; written as NOT IN on purpose, so a
  new reason is covered until a migration says it may repeat.

The same table is `RULES` in app/modules/wallet/rules.py, written out here
rather than imported, because a migration never changes after it merges (rule
11). tests/modules/wallet/test_guards.py proves the two agree, every reason
against every sign and every ref type.

Every environment had no ledger row when this was written: nothing could write
one before T-5.1. A row that broke these rules would make the upgrade fail,
naming the constraint, which is the point.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97ddae55f597"
down_revision: str | Sequence[str] | None = "684b79a19e8b"
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
DEBITS = (
    "gift",
    "thread_open",
    "dm_open",
    "thread_reopen",
    "voice_unlock",
    "album_request",
    "super_like",
    "liked_you_reveal",
)
REF_TYPES = (
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
REF_OPTIONAL = "admin_grant"
REPEATS = ("admin_grant", "thread_reopen")


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


DIRECTION = (
    f"(reason IN ({_sql_list(CREDITS)}) AND delta > 0) "
    f"OR (reason IN ({_sql_list(DEBITS)}) AND delta < 0)"
)
REF_REQUIRED = f"reason = '{REF_OPTIONAL}' OR ref_id IS NOT NULL"
REF_TYPE = "ref_type IS NULL OR (reason, ref_type) IN ({})".format(
    ", ".join(f"('{reason}', '{ref_type}')" for reason, ref_type in REF_TYPES)
)
ONE_PER_EVENT_WHERE = f"reason NOT IN ({_sql_list(REPEATS)})"

CHECKS = (
    ("reason_direction", DIRECTION),
    ("ref_required", REF_REQUIRED),
    ("reason_ref_type", REF_TYPE),
)


def upgrade() -> None:
    """Upgrade schema."""
    for name, condition in CHECKS:
        op.create_check_constraint(
            op.f(f"ck_ledger_entries_{name}"), "ledger_entries", condition
        )
    op.create_index(
        "uq_ledger_entries_one_per_event",
        "ledger_entries",
        ["user_id", "reason", "ref_type", "ref_id"],
        unique=True,
        postgresql_where=sa.text(ONE_PER_EVENT_WHERE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_ledger_entries_one_per_event", table_name="ledger_entries")
    for name, _ in reversed(CHECKS):
        op.drop_constraint(op.f(f"ck_ledger_entries_{name}"), "ledger_entries")
